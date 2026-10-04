"""启动默认不改库；显式初始化单独验收，不连接真实数据库。"""
import ast
import asyncio
import importlib.util
import logging
import os
import sys
import unittest
from contextlib import asynccontextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock, patch

BACKEND = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('offline_startup_database', BACKEND / 'database.py')
database = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = database
spec.loader.exec_module(database)


class DatabaseStartupTests(unittest.TestCase):
    def setUp(self):
        self.enterContext(patch.dict(os.environ, {'FUND_DATABASE_INIT_MODE': 'check', 'DATABASE_URL': 'postgresql://offline/test'}))
        self.enterContext(patch('sqlalchemy.create_engine', side_effect=AssertionError('Real database forbidden')))
        database._checked_database_url = None
        database._initialized_database_url = None
        self.health = self.enterContext(patch.object(database, 'check_database_health', return_value={'status': 'ok'}))
        self.engine = MagicMock()
        self.conn = self.engine.connect.return_value.__enter__.return_value = Mock()
        self.enterContext(patch.object(database, 'get_engine', return_value=self.engine))

    def test_default_and_lazy_repository_initialization_only_check(self):
        self.assertTrue(database.init_database())
        calls = list(self.conn.execute.call_args_list)
        self.assertGreater(len(calls), 0)
        self.assertTrue(all(str(call.args[0]).lstrip().startswith('SELECT') for call in calls))
        self.assertTrue(database.init_database())
        self.assertEqual(calls, self.conn.execute.call_args_list)
        self.health.assert_called_once_with(min_fund_count=1)
        self.engine.begin.assert_not_called()

    def test_missing_database_blocks_without_fallback_ddl(self):
        self.health.return_value = {'status': 'schema_missing'}
        with self.assertRaises(RuntimeError):
            database.init_database()
        self.engine.connect.assert_not_called()
        self.assertIsNone(database._checked_database_url)

    def test_missing_core_column_blocks_without_ddl(self):
        self.conn.execute.side_effect = RuntimeError('Missing column')
        with self.assertRaises(RuntimeError):
            database.prepare_database('check')
        self.engine.begin.assert_not_called()
        self.assertIsNone(database._checked_database_url)

    def test_invalid_mode_is_rejected_even_after_success(self):
        database.init_database()
        with self.assertRaises(ValueError):
            database.init_database('typo')
        with patch.dict(os.environ, {'FUND_DATABASE_INIT_MODE': 'typo'}):
            with self.assertRaises(ValueError):
                database.init_database()

    def test_initialization_requires_explicit_mode(self):
        initializer = self.enterContext(patch.object(database, '_initialize_database_schema', return_value=True))
        database.init_database()
        initializer.assert_not_called()
        self.assertTrue(database.init_database('initialize'))
        initializer.assert_called_once_with()
        with patch.dict(os.environ, {'FUND_DATABASE_INIT_MODE': 'initialize'}):
            self.assertTrue(database.prepare_database())
        self.assertEqual(2, initializer.call_count)

    def test_explicit_initializer_failure_does_not_start_service(self):
        with patch.object(database, '_initialize_database_schema', return_value=False):
            self.assertFalse(database.init_database('initialize'))
            with self.assertRaises(RuntimeError):
                database.prepare_database('initialize')

    def test_new_database_configuration_is_checked_again(self):
        database.init_database()
        with patch.dict(os.environ, {'DATABASE_URL': 'postgresql://offline/other'}):
            database.init_database()
        self.assertEqual(2, self.health.call_count)

    def load_app_functions(self):
        path = BACKEND / 'main.py'
        nodes = [node for node in ast.parse(path.read_text()).body
                 if getattr(node, 'name', None) in ('lifespan', 'health_check')]
        for node in nodes:
            if node.name == 'health_check':
                node.decorator_list = []
        namespace = {'asynccontextmanager': asynccontextmanager, 'os': os,
                     'logger': logging.getLogger('offline_startup'),
                     'get_data_service': lambda: SimpleNamespace(mock_mode=False),
                     'get_scoring_engine': lambda: None, 'FastAPI': object,
                     'NAV_STORAGE_CONTRACT_VERSION': 'batch_provenance_v1',
                     'METRIC_STORAGE_CONTRACT_VERSION': 'batch_revision_archive_v1'}
        exec(compile(ast.Module(body=nodes, type_ignores=[]), str(path), 'exec'), namespace)
        return namespace

    def test_lifespan_and_health_report_actual_started_mode(self):
        namespace = self.load_app_functions()
        app = SimpleNamespace(state=SimpleNamespace())
        namespace['app'] = app
        cache = SimpleNamespace(get_cache=lambda: object())
        self.enterContext(patch.dict(sys.modules, {
            'database': database, 'services.cache_service': cache,
            'service_registry': SimpleNamespace(DATA_SOURCE='tushare')}))

        async def run():
            async with namespace['lifespan'](app):
                with patch.dict(os.environ, {'FUND_DATABASE_INIT_MODE': 'initialize'}):
                    result = await namespace['health_check']()
                self.assertEqual('check', result['database_init_mode'])
                self.assertEqual('batch_provenance_v1', result['storage_contract']['nav'])
                self.assertEqual('batch_revision_archive_v1', result['storage_contract']['metrics'])
                self.assertEqual(os.getpid(), result['runtime_pid'])
        asyncio.run(run())
        self.engine.begin.assert_not_called()

    def test_lifespan_failure_is_not_swallowed(self):
        namespace = self.load_app_functions()
        self.health.return_value = {'status': 'database_unavailable'}
        self.enterContext(patch.dict(sys.modules, {
            'database': database, 'services.cache_service': SimpleNamespace(get_cache=lambda: object())}))

        async def run():
            async with namespace['lifespan'](SimpleNamespace(state=SimpleNamespace())):
                self.fail('Unhealthy database must not start the service')
        with self.assertRaises(RuntimeError):
            asyncio.run(run())


if __name__ == '__main__':
    unittest.main()
