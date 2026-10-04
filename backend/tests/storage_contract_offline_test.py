"""保存契约离线验收：模拟事务，不连接数据库、不调用供应商。"""
import copy
import ast
import __future__
import importlib.util
import json
import logging
import math
import sys
import unittest
from contextlib import contextmanager
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))


def load(relative):
    spec = importlib.util.spec_from_file_location(Path(relative).stem, BACKEND / relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


nav_module = load('repositories/nav_repo.py')
metric_module = load('repositories/metric_snapshot_repo.py')
evidence_module = load('services/fund_nav_evidence_service.py')


def ranking_functions(namespace):
    """加载真实函数，跳过脚本级配置加载和无关服务导入。"""
    path = BACKEND / 'scripts/sync_fund_ranking_metrics.py'
    names = {'number_or_none', 'save_latest_fund_facts', 'save_enrichment_metric_facts',
             'invalidate_nav_derived_evaluation_facts', 'sync_one_fund'}
    nodes = [node for node in ast.parse(path.read_text()).body
             if isinstance(node, ast.FunctionDef) and node.name in names]
    namespace.update(json=json, date=date, datetime=datetime, UTC=UTC, Decimal=Decimal)
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(path), 'exec',
                 flags=__future__.annotations.compiler_flag), namespace)
    return namespace


def isolated_service(relative, namespace):
    path = BACKEND / relative
    tree = ast.parse(path.read_text())
    tree.body = [node for node in tree.body if not
                 (isinstance(node, ast.ImportFrom) and (node.module or '').startswith('services.'))]
    exec(compile(tree, str(path), 'exec', flags=__future__.annotations.compiler_flag), namespace)
    return namespace


class Result:
    def __init__(self, rows=()):
        self.rows = list(rows)

    def fetchone(self):
        return SimpleNamespace(_mapping=self.rows[0]) if self.rows else None

    def mappings(self):
        return self

    def first(self):
        return self.rows[0] if self.rows else None

    def __iter__(self):
        return iter(self.rows)

    def fetchall(self):
        return [SimpleNamespace(**row) for row in self.rows]


class MemoryTransaction:
    """只模拟仓储实际使用的语句；未知 SQL 立即失败。"""
    def __init__(self, columns=None):
        self.columns = columns or {}
        self.metrics = []
        self.nav = []
        self.calls = []
        self.commits = 0
        self.rollbacks = 0
        self.fail_latest = False

    @contextmanager
    def begin(self):
        before = copy.deepcopy((self.metrics, self.nav))
        try:
            yield self
        except Exception:
            self.metrics, self.nav = before
            self.rollbacks += 1
            raise
        else:
            self.commits += 1

    @contextmanager
    def connect(self):
        yield self

    def execute(self, statement, params=None):
        sql = ' '.join(str(statement).split())
        self.calls.append((sql, copy.deepcopy(params)))
        if 'FROM pg_attribute' in sql:
            return Result([{'name': name, 'data_type': kind} for name, kind in self.columns.items()])
        if 'pg_advisory_xact_lock' in sql:
            return Result()
        if sql.startswith('DELETE FROM fund_nav'):
            self.nav = []
            return Result()
        if sql.startswith('INSERT INTO fund_nav'):
            for item in params:
                date.fromisoformat(str(item['trade_date']))
                self.nav.append(copy.deepcopy(item))
            return Result()
        if sql.startswith('UPDATE funds'):
            if self.fail_latest:
                raise RuntimeError('simulated latest update failure')
            return Result()
        if 'FROM fund_nav' in sql:
            return Result(self.nav)
        if sql.startswith('SELECT * FROM metric_snapshots'):
            fields = ('target_type', 'target_id', 'as_of_date', 'metric_name', 'benchmark_code', 'peer_group_key')
            return Result([row for row in self.metrics if all(row.get(key) == params.get(key) for key in fields)
                           and row.get('metric_window') == params.get('window')])
        if sql.startswith(('INSERT INTO metric_snapshots', 'UPDATE metric_snapshots')):
            if params.get('source_snapshot_id') == 'invalid':
                raise RuntimeError('simulated invalid source UUID')
            record = copy.deepcopy(params)
            record['metric_window'] = record.pop('window')
            record['details'] = json.loads(record['details']) if record['details'] is not None else None
            record['id'] = record.get('id') or str(len(self.metrics) + 1)
            record['updated_at'] = len(self.calls)
            self.metrics = [row for row in self.metrics if row['id'] != record['id']]
            self.metrics.append(record)
            return Result([record])
        raise AssertionError('Unexpected SQL: ' + sql)


class StorageContractTest(unittest.TestCase):
    def setUp(self):
        self.guard = patch('sqlalchemy.create_engine', side_effect=AssertionError('Real database forbidden'))
        self.guard.start()
        self.addCleanup(self.guard.stop)

    def nav_repo(self, columns=None):
        repo = nav_module.NavRepo()
        repo._engine = MemoryTransaction(columns)
        return repo

    def metric_repo(self):
        repo = metric_module.MetricSnapshotRepo()
        repo._engine = MemoryTransaction()
        return repo

    def record(self, **changes):
        return dict(target_type='fund', target_id='OFFLINE', as_of_date=date(2026, 10, 3),
                    metric_name='annualized_return', metric_value=Decimal('.1'), window='1y',
                    metric_unit='ratio', details={'methodology_version': 'old'}, **changes)

    def test_old_partial_and_new_schema_without_ddl(self):
        for columns in ({}, {'benchmark_code': 'text'}, nav_module.NAV_PROVENANCE_COLUMNS):
            with self.subTest(columns=columns):
                repo = self.nav_repo(columns)
                self.assertTrue(repo.upsert_nav_series('OFFLINE', [{'date': '2026-10-01', 'nav': 1.1}]))
                insert, params = repo.engine.calls[-1]
                for column in nav_module.NAV_PROVENANCE_COLUMNS:
                    self.assertEqual(column in params[0], column in columns)
                self.assertFalse(any('ALTER TABLE' in sql or 'CREATE TABLE' in sql for sql, _ in repo.engine.calls))

    def test_missing_benchmark_preserves_but_explicit_null_clears(self):
        repo = self.nav_repo(nav_module.NAV_PROVENANCE_COLUMNS)
        rows = [{'date': '2026-10-01', 'nav': 1.1},
                {'date': '2026-10-02', 'nav': 1.2, 'benchmark_nav': None,
                 'benchmark_code': 'OLD', 'benchmark_source': 'old', 'adj_nav_source': 'old'},
                {'date': '2026-10-03', 'nav': 1.3, 'benchmark_nav': 100}]
        self.assertTrue(repo.upsert_nav_series('OFFLINE', rows))
        sql, batch = repo.engine.calls[-1]
        self.assertIn('CASE WHEN :benchmark_provided', sql)
        self.assertEqual([False, True, True], [row['benchmark_provided'] for row in batch])
        for row in batch:
            self.assertIsNone(row['benchmark_code'])
            self.assertIsNone(row['benchmark_source'])
            self.assertIsNone(row['adj_nav_source'])

    def test_failed_nav_batch_restores_replaced_range(self):
        repo = self.nav_repo()
        original = [{'date': '2026-09-01', 'nav': 1}]
        repo.engine.nav = copy.deepcopy(original)
        self.assertFalse(repo.upsert_nav_series('OFFLINE', [
            {'date': '2026-10-01', 'nav': 1.1}, {'date': 'bad-date', 'nav': 1.2}], replace_range=True))
        self.assertEqual(original, repo.engine.nav)
        self.assertEqual(1, repo.engine.rollbacks)
        self.assertEqual(0, repo.engine.commits)

    def test_latest_update_failure_rolls_back_nav(self):
        repo = self.nav_repo()
        repo.engine.fail_latest = True
        self.assertFalse(repo.upsert_nav_series('OFFLINE', [{'date': '2026-10-01', 'nav': 1}], update_latest=True))
        self.assertEqual([], repo.engine.nav)

    def test_empty_nav_does_not_delete_range(self):
        repo = self.nav_repo()
        self.assertFalse(repo.upsert_nav_series('OFFLINE', [], replace_range=True))
        self.assertEqual([], repo.engine.calls)

    def test_nav_read_preserves_date_contract_and_exposes_missing_sources(self):
        repo = self.nav_repo()
        repo.engine.nav = [{'trade_date': date(2026, 10, 1), 'unit_nav': Decimal('1.1'),
                            'accum_nav': None, 'adj_nav': None, 'daily_return': None, 'benchmark_nav': None,
                            **{name: None for name in nav_module.NAV_PROVENANCE_COLUMNS}}]
        row = repo.get_nav_series('OFFLINE')[0]
        self.assertEqual(date(2026, 10, 1), row['date'])
        self.assertEqual(row['nav'], row['unit_nav'])
        self.assertIsNone(row['adj_nav_source'])
        self.assertIn('NULL AS announcement_date', repo.engine.calls[-1][0])

    def test_nullable_metric_key_is_idempotent_and_revisions_are_preserved(self):
        repo = self.metric_repo()
        record = self.record()
        first = repo.upsert_metric(**record)
        repeated = repo.upsert_metrics([record])[0]
        self.assertEqual(first, repeated)
        updated = repo.upsert_metrics([{**record, 'metric_value': Decimal('.2'), 'details': {'methodology_version': 'new'}}])[0]
        self.assertEqual(first['id'], updated['id'])
        history = updated['details']['_revision_history']
        self.assertEqual('0.10000000', history[0]['metric_value'])
        self.assertEqual(record['details'], history[0]['details'])
        self.assertEqual(1, len(repo.engine.metrics))
        lookup = next(sql for sql, _ in repo.engine.calls if 'LIMIT 1 FOR UPDATE' in sql)
        self.assertIn('IS NOT DISTINCT FROM :benchmark_code', lookup)

    def test_missing_method_does_not_inherit_previous_method(self):
        repo = self.metric_repo()
        repo.upsert_metric(**self.record())
        updated = repo.upsert_metric(**{**self.record(), 'metric_value': Decimal('.2'), 'details': None})
        self.assertNotIn('methodology_version', updated['details'])
        self.assertEqual('old', updated['details']['_revision_history'][0]['details']['methodology_version'])

    def test_metric_batch_failure_rolls_back_first_revision(self):
        repo = self.metric_repo()
        before = repo.upsert_metric(**self.record())
        with self.assertRaises(RuntimeError):
            repo.upsert_metrics([{**self.record(), 'metric_value': Decimal('.2')},
                                 {**self.record(), 'metric_name': 'max_drawdown', 'source_snapshot_id': 'invalid'}])
        self.assertEqual(before['metric_value'], str(repo.engine.metrics[0]['metric_value']))
        self.assertNotIn('_revision_history', repo.engine.metrics[0]['details'])

    def test_duplicate_and_nonfinite_batches_are_not_saved(self):
        repo = self.metric_repo()
        with self.assertRaises(ValueError):
            repo.upsert_metrics([self.record(), self.record()])
        for value in ('NaN', 'Infinity'):
            with self.assertRaises(ValueError):
                repo.upsert_metrics([self.record(), {**self.record(), 'metric_name': 'sharpe_ratio', 'metric_value': value}])
        self.assertEqual([], repo.engine.metrics)
        self.assertEqual([], repo.upsert_metrics([]))

    def test_incoming_history_cannot_overwrite_stored_history(self):
        repo = self.metric_repo()
        original = repo.upsert_metric(**self.record())
        repeated = repo.upsert_metric(**{**self.record(), 'details': {**self.record()['details'], '_revision_history': ['fake']}})
        self.assertEqual(original, repeated)

    def test_sources_are_attached_to_matching_dates_only(self):
        rows, count = evidence_module.FundNavEvidenceService().attach_benchmark_nav(
            [{'date': '2026-10-01', 'benchmark_nav': 999, 'benchmark_source': 'old'},
             {'date': '2026-10-02'}, {'date': '2026-10-03'}],
            [{'date': '2026-10-01', 'nav': 101, 'benchmark_code': 'WRONG', 'source': 'wrong'},
             {'date': '2026-10-02', 'nav': 102, 'benchmark_code': 'INDEX', 'source': 'vendor.index'}], 'INDEX')
        self.assertEqual(1, count)
        self.assertIsNone(rows[0]['benchmark_nav'])
        self.assertIsNone(rows[0]['benchmark_source'])
        self.assertEqual('INDEX', rows[1]['benchmark_code'])
        self.assertEqual('vendor.index', rows[1]['benchmark_source'])
        self.assertIsNone(rows[2]['benchmark_nav'])

    def test_archive_and_fund_cleanup_share_transaction_and_cache_waits_for_commit(self):
        engine = MemoryTransaction()
        original = [self.record()]
        engine.metrics = copy.deepcopy(original)
        cache = Mock()

        def archive(connection, code, validation):
            self.assertIs(engine, connection)
            cache.assert_not_called()
            connection.metrics = []
            return {'archive_id': 'archive-1', 'archived_metrics': 1}

        from sqlalchemy import text
        namespace = ranking_functions({'get_engine': lambda: engine, 'text': text,
                                       'archive_invalid_nav_metrics': archive})
        with patch.dict(sys.modules, {'services.cache_service': SimpleNamespace(invalidate_fund_cache=cache)}):
            engine.fail_latest = True
            with self.assertRaises(RuntimeError):
                namespace['invalidate_nav_derived_evaluation_facts']('OFFLINE', {'status': 'invalid'})
            self.assertEqual(original, engine.metrics)
            cache.assert_not_called()
            engine.fail_latest = False
            result = namespace['invalidate_nav_derived_evaluation_facts']('OFFLINE', {'status': 'invalid'})
            self.assertEqual(1, engine.commits)
            cache.assert_called_once_with('OFFLINE')
            self.assertEqual('archive-1', result['archive_id'])
            marker = json.loads(engine.calls[-1][1]['marker'])
            self.assertEqual('archive-1', marker['ranking_metrics']['archive_id'])

    def test_archive_count_mismatch_is_a_failure_not_success(self):
        conn = Mock()
        conn.execute.return_value.mappings.return_value.first.return_value = {
            'id': 'archive-1', 'record_count': 2, 'removed_count': 1}
        with self.assertRaises(RuntimeError):
            metric_module.archive_invalid_nav_metrics(conn, 'OFFLINE', {'status': 'invalid'})

    def test_each_auxiliary_fact_group_is_one_batch(self):
        repo = SimpleNamespace(upsert_metrics=Mock(side_effect=lambda records: records))
        scorer = SimpleNamespace(metric_facts_from_fund=lambda fund: {'latest': {'expense_ratio': .01, 'aum': 5}})
        namespace = ranking_functions({'ProfessionalScoringService': lambda: scorer})
        self.assertEqual(2, namespace['save_latest_fund_facts'](repo, 'OFFLINE', {}, date(2026, 10, 3)))
        repo.upsert_metrics.assert_called_once()
        repo.upsert_metrics.reset_mock()
        self.assertEqual(4, namespace['save_enrichment_metric_facts'](repo, 'OFFLINE', {
            'benchmark_code': 'DR007', 'performance_facts': {
                'seven_day_annualized_yield': .02, 'income_per_10000': .5,
                'benchmark_annualized_rate': .015, 'benchmark_yield_spread': .005}}, date(2026, 10, 3)))
        repo.upsert_metrics.assert_called_once()

    def test_failed_nav_save_stops_calculation_and_invalidation(self):
        for status in ('valid', 'invalid'):
            with self.subTest(status=status):
                rows = [{'date': '2026-10-01', 'nav': 1}] * 20
                nav_repo = SimpleNamespace(upsert_nav_series=Mock(return_value=False))
                roller, invalidate = Mock(), Mock()
                namespace = ranking_functions({
                    'get_fund_repo': lambda: SimpleNamespace(get_fund=lambda code: {'type': 'stock'}),
                    'get_nav_repo': lambda: nav_repo,
                    'get_metric_snapshot_repo': lambda: None,
                    'get_fund_classification_repo': lambda: SimpleNamespace(get_classification_context=lambda code: {'status': 'resolved'}),
                    'FundNavDataEnrichmentService': lambda source: SimpleNamespace(enrich=lambda **kw: {'nav_series': rows, 'nav_data_status': status}),
                    'mark_ranking_sync_unavailable': Mock(),
                })
                namespace['invalidate_nav_derived_evaluation_facts'] = invalidate
                result = namespace['sync_one_fund'](SimpleNamespace(get_fund_nav=lambda *a, **kw: rows),
                                                    roller, 'OFFLINE', date(2026, 1, 1), date(2026, 10, 3))
                self.assertEqual('failed', result['status'])
                roller.calculate_and_save_for_fund.assert_not_called()
                invalidate.assert_not_called()

    def test_cache_invalidation_clears_target_charts_and_preserves_other_details(self):
        module = load('services/cache_service.py')
        cache = module.MemoryCache()
        keys = ('fund:detail:v10:OFFLINE', 'fund:detail:v10:OTHER',
                'fund:nav:v2:OFFLINE:window', 'fund:nav-chart:OFFLINE:1y',
                'fund:nav-chart:OTHER:1y', 'fund:list:page1')
        for key in keys:
            cache.set(key, key)
        with patch.object(module, 'get_cache', return_value=cache):
            module.invalidate_fund_cache('OFFLINE')
        for key in keys:
            self.assertEqual(key if 'OTHER' in key else None, cache.get(key))

    def test_rolling_and_manager_tenure_submit_one_complete_batch_each(self):
        factory = load('services/metric_factory.py').MetricFactory
        rolling = isolated_service('services/rolling_metric_service.py', {'MetricFactory': factory})['RollingMetricService']
        coverage = load('services/manager_tenure_coverage.py').build_manager_tenure_coverage
        manager = isolated_service('services/manager_tenure_metric_service.py', {
            'MetricFactory': factory, 'build_manager_tenure_coverage': coverage,
            'resolve_manager_tenure_context': lambda fund, profile, context: context})['ManagerTenureMetricService']
        rows = [{'date': date(2026, 1, 1) + timedelta(days=i), 'accum_nav': 1 + .001 * i} for i in range(100)]
        classification = SimpleNamespace(get_classification_context=lambda code: {'peer_group_key': 'peer'})
        repo = SimpleNamespace(upsert_metrics=Mock(side_effect=lambda records: [
            {**record, 'metric_window': record['window']} for record in records]))
        getters = SimpleNamespace(
            get_nav_repo=lambda: SimpleNamespace(get_nav_series=lambda *a, **kw: rows),
            get_metric_snapshot_repo=lambda: repo,
            get_fund_classification_repo=lambda: classification,
            get_research_profile_repo=lambda: SimpleNamespace(get_profile=lambda code: {}),
            get_fund_repo=lambda: SimpleNamespace(get_fund_by_identifier=lambda code: {}))
        manager_repo = SimpleNamespace(get_current_fund_tenure_context=lambda code: {'start_date': '2026-01-01', 'source': 'fixture'})
        services = (rolling(), manager(manager_repo=manager_repo, classification_repo=classification))
        with patch.dict(sys.modules, {'repositories': getters}):
            for service in services:
                repo.upsert_metrics.reset_mock()
                result = service.calculate_and_save_for_fund('OFFLINE', source_snapshot_id='fixture')
                repo.upsert_metrics.assert_called_once()
                records = repo.upsert_metrics.call_args.args[0]
                self.assertEqual(len(records), result['saved'])
                self.assertGreater(result['saved'], 2)
                self.assertTrue(all(row['source_snapshot_id'] == 'fixture' for row in records))
                self.assertTrue(all(row['peer_group_key'] == 'peer' for row in records))

    def test_tushare_point_provenance_and_missing_announcement(self):
        import pandas as pd
        path = BACKEND / 'services/tushare_service.py'
        names = {'TushareDataService', '_to_ts_code', '_as_float'}
        nodes = [node for node in ast.parse(path.read_text()).body if getattr(node, 'name', None) in names]
        namespace = {'pd': pd, 'math': math, 'datetime': datetime, 'timedelta': timedelta,
                     'logger': logging.getLogger('offline')}
        exec(compile(ast.Module(body=nodes, type_ignores=[]), str(path), 'exec',
                     flags=__future__.annotations.compiler_flag), namespace)
        source = namespace['TushareDataService'].__new__(namespace['TushareDataService'])
        source.mock_mode = False
        source._strict_fail = Mock(side_effect=AssertionError('Unexpected provider failure'))
        source._pro = SimpleNamespace(fund_nav=Mock(return_value=pd.DataFrame([
            {'nav_date': '20261001', 'ann_date': '20261002', 'unit_nav': 1.1, 'adj_nav': 2.1, 'accum_nav': 1.9},
            {'nav_date': '20261002', 'ann_date': float('nan'), 'unit_nav': 1.2, 'adj_nav': 2.2, 'accum_nav': 2.0}])))
        rows = source.get_fund_nav('000001.OF', '2026-10-01', '2026-10-02')
        self.assertEqual('2026-10-02', rows[0]['announcement_date'])
        self.assertIsNone(rows[1]['announcement_date'])
        self.assertEqual('tushare.fund_nav.adj_nav', rows[0]['adj_nav_source'])
        self.assertEqual(1.9, rows[0]['reported_accum_nav'])


if __name__ == '__main__':
    unittest.main()
