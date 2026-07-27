#!/bin/bash

# 基金经理评价分析系统 - 快速启动脚本

set -e

echo "🚀 基金经理评价分析系统 - 快速启动"
echo "=================================="
echo ""

# 检查 Node.js
if ! command -v node &> /dev/null; then
    echo "❌ 错误: 未安装 Node.js"
    echo "请访问 https://nodejs.org/ 安装 Node.js 18+"
    exit 1
fi

echo "✅ Node.js 版本: $(node --version)"

# 检查 PostgreSQL
if ! command -v psql &> /dev/null; then
    echo "⚠️  警告: 未检测到 PostgreSQL"
    echo "请确保 PostgreSQL 15+ 已安装并运行"
fi

# 检查 .env.local
if [ ! -f .env.local ]; then
    echo ""
    echo "📝 创建环境变量文件..."
    cp .env.example .env.local
    echo "✅ 已创建 .env.local"
    echo "⚠️  请编辑 .env.local 填入实际的 API Keys"
    echo ""
    read -p "按 Enter 继续..."
fi

# 安装依赖
if [ ! -d "node_modules" ]; then
    echo ""
    echo "📦 安装依赖..."
    npm install
    echo "✅ 依赖安装完成"
fi

# 检查数据库
echo ""
echo "🗄️  检查数据库..."
if npx prisma db pull 2>/dev/null; then
    echo "✅ 数据库连接成功"
else
    echo "⚠️  数据库连接失败，尝试初始化..."

    # 启动数据库
    if [ -f "scripts/start-db.sh" ]; then
        echo "启动 PostgreSQL..."
        ./scripts/start-db.sh &
        sleep 3
    fi

    # 运行迁移
    echo "运行数据库迁移..."
    npx prisma migrate dev --name init
    npx prisma generate
    echo "✅ 数据库初始化完成"
fi

# 启动应用
echo ""
echo "🎉 启动应用..."
echo "=================================="
echo ""
echo "访问地址: http://localhost:3000"
echo ""
echo "可用页面:"
echo "  - 基金列表: http://localhost:3000/funds"
echo "  - 基金经理: http://localhost:3000/managers"
echo "  - 调研报告: http://localhost:3000/reports"
echo "  - 基金研究: http://localhost:3000/analysis"
echo "  - 筛选器: http://localhost:3000/screening"
echo "  - 数据同步: http://localhost:3000/sync"
echo ""
echo "按 Ctrl+C 停止服务"
echo ""

npm run dev
