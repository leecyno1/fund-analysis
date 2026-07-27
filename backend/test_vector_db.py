"""
测试向量数据库集成
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from services.vector_db_service import get_vector_db
import uuid

def test_vector_db():
    print("=" * 60)
    print("测试向量数据库集成")
    print("=" * 60)

    try:
        # 1. 获取向量数据库实例
        print("\n1. 连接向量数据库...")
        vector_db = get_vector_db()
        print("✓ 连接成功")

        # 2. 获取集合信息
        print("\n2. 获取集合信息...")
        info = vector_db.get_collection_info()
        print(f"✓ 集合名称: {info.get('name')}")
        print(f"✓ 向量数量: {info.get('vectors_count', 0)}")
        print(f"✓ 点数量: {info.get('points_count', 0)}")
        print(f"✓ 状态: {info.get('status')}")

        # 3. 添加测试研报
        print("\n3. 添加测试研报...")
        test_id = str(uuid.uuid4())
        vector_db.add_report(
            report_id=test_id,
            title="测试研报 - 某某基金经理调研",
            content="该基金经理专注于价值投资，偏好低估值蓝筹股。投资风格稳健，注重风险控制。",
            metadata={
                "manager_name": "张三",
                "company": "华夏基金",
                "date": "2026-04-25",
                "tags": ["价值投资", "蓝筹股"]
            }
        )
        print(f"✓ 添加成功，ID: {test_id}")

        # 4. 语义搜索
        print("\n4. 测试语义搜索...")
        query = "价值投资风格的基金经理"
        results = vector_db.search_similar(query, top_k=3)
        print(f"✓ 查询: {query}")
        print(f"✓ 找到 {len(results)} 条相似结果:")
        for i, result in enumerate(results, 1):
            print(f"  {i}. {result.get('title')} (相似度: {result.get('similarity', 0):.3f})")
            print(f"     经理: {result.get('manager_name', 'N/A')}")

        # 5. 清理测试数据
        print("\n5. 清理测试数据...")
        vector_db.delete_report(test_id)
        print("✓ 清理完成")

        print("\n" + "=" * 60)
        print("✓ 所有测试通过！向量数据库集成正常工作")
        print("=" * 60)

        return True

    except Exception as e:
        print(f"\n✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_vector_db()
    sys.exit(0 if success else 1)
