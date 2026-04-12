# GitHub 上传指南

## 📋 上传前准备

### 1. 确认文件清单

**必须上传的文件**：
- ✅ 所有Python源代码（`.py`文件）
- ✅ `requirements.txt` - 依赖清单
- ✅ `README.md` - 项目说明
- ✅ `UI_README.md` - UI使用说明
- ✅ `config.yaml.template` - 配置文件模板
- ✅ `.gitignore` - Git忽略配置
- ✅ `.github/workflows/screener.yml` - GitHub Actions配置
- ✅ `ui/styles/dark_theme.qss` - UI样式文件

**不要上传的文件**：
- ❌ `config.yaml` - 包含真实API密钥
- ❌ `build/` 和 `dist/` - 打包生成的文件
- ❌ `__pycache__/` - Python缓存
- ❌ `*.log` - 日志文件
- ❌ `*.csv`, `*.json` - 数据文件

### 2. 检查.gitignore

确保 `.gitignore` 文件包含以下内容：
```
# Config with sensitive info
config.yaml
.env
*.pem
*.key

# PyInstaller
*.spec
build/
dist/

# Python
__pycache__/
*.py[cod]
```

## 🚀 上传步骤

### 方式1：使用Git命令行

```bash
# 1. 初始化Git仓库（如果还没有）
git init

# 2. 添加远程仓库
git remote add origin https://github.com/你的用户名/JusticePlutus.git

# 3. 添加所有文件
git add .

# 4. 查看将要提交的文件
git status

# 5. 提交更改
git commit -m "Initial commit: JusticePlutus A股选股系统"

# 6. 推送到GitHub
git push -u origin main
```

### 方式2：使用GitHub Desktop

1. 打开GitHub Desktop
2. File → Add Local Repository
3. 选择 `JusticePlutus` 文件夹
4. 点击 "Create a new repository on GitHub"
5. 填写仓库信息并点击 "Create repository"
6. 点击 "Publish repository"

### 方式3：直接上传到GitHub网页

1. 访问 https://github.com/new
2. 创建新仓库（不要勾选 "Add a README file"）
3. 点击 "uploading an existing file"
4. 拖拽文件或点击选择文件
5. 填写提交信息并点击 "Commit changes"

## ⚙️ GitHub Secrets 配置

上传后，需要在GitHub仓库中配置Secrets：

1. 进入仓库页面
2. Settings → Secrets and variables → Actions
3. 点击 "New repository secret"
4. 添加以下Secrets：

| Secret名称 | 说明 | 是否必需 |
|-----------|------|---------|
| `TUSHARE_TOKEN` | Tushare API Token | 可选 |
| `JQ_USERNAME` | JoinQuant用户名 | 可选 |
| `JQ_PASSWORD` | JoinQuant密码 | 可选 |
| `MAIRUI_TOKEN` | 迈瑞API Token | 可选 |
| `WECOM_WEBHOOK_URL` | 企业微信Webhook | 可选 |
| `LITELLM_MODEL` | LiteLLM模型 | 可选 |
| `DEEPSEEK_API_KEY` | Deepseek API Key | 可选 |
| `GEMINI_API_KEY` | Gemini API Key | 可选 |

## 📝 README.md 建议

确保 `README.md` 包含以下内容：

1. **项目简介** - 简要说明项目功能
2. **功能特性** - 列出主要功能
3. **安装说明** - 如何安装依赖
4. **使用方法** - 如何运行程序
5. **配置说明** - 如何配置API密钥
6. **注意事项** - 重要提醒

## ⚠️ 安全提醒

### 不要上传敏感信息！

- ❌ **API密钥** - 不要在代码中硬编码
- ❌ **密码** - 不要提交包含密码的配置文件
- ❌ **私钥文件** - 不要上传 `.pem`, `.key` 文件

### 使用环境变量

在GitHub Actions中使用Secrets：
```yaml
env:
  TUSHARE_TOKEN: ${{ secrets.TUSHARE_TOKEN }}
```

在本地使用环境变量：
```bash
export TUSHARE_TOKEN="your_token_here"
```

## 🔄 更新仓库

后续更新代码时：

```bash
# 查看更改
git status

# 添加更改的文件
git add .

# 提交更改
git commit -m "描述你的更改"

# 推送到GitHub
git push
```

## 📊 检查上传结果

上传完成后，检查：

1. ✅ GitHub仓库页面是否显示所有文件
2. ✅ `.gitignore` 是否生效（敏感文件不应显示）
3. ✅ README.md 是否正确渲染
4. ✅ GitHub Actions是否能正常运行

## 🆘 常见问题

### Q: 如何撤销已上传的敏感文件？

```bash
# 从Git历史中删除文件
git filter-branch --force --index-filter \
  "git rm --cached --ignore-unmatch config.yaml" \
  --prune-empty --tag-name-filter cat -- --all

# 强制推送
git push origin --force --all
```

### Q: 如何更新.gitignore？

```bash
# 清除Git缓存
git rm -r --cached .

# 重新添加文件
git add .

# 提交更改
git commit -m "Update .gitignore"
```

### Q: 文件太大无法上传？

- 使用Git LFS（Large File Storage）
- 或者不上传大文件（数据文件、模型文件等）

## 📚 相关文档

- [GitHub文档](https://docs.github.com)
- [Git教程](https://git-scm.com/book/zh/v2)
- [GitHub Actions文档](https://docs.github.com/en/actions)
