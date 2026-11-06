# 部署准备

本项目提供两个运行入口：

- 本地开发：`python3 -m fuqianhecha.web`
- 服务器部署：Docker 中使用 Gunicorn 运行 `fuqianhecha.web:application`

## 本地 Docker 验证

1. 确保 Docker Desktop 已启动。
2. 可选：复制 `.env.example` 为 `.env`，只修改本机映射端口。
3. 在项目根目录运行 `docker compose up --build`。
4. 打开 `http://127.0.0.1:8000`。
5. 查看健康检查：`http://127.0.0.1:8000/api/health`。
6. 验证完成后运行 `docker compose down`。

## 安全边界

- `.env` 和 `.env.*` 已被 Git 与 Docker 构建上下文忽略，只有 `.env.example` 可以提交。
- 镜像只复制运行所需的程序、网页与已审核知识库，不包含测试、文档、开发案例或隐藏评估集。
- 容器使用非 root 用户、只读文件系统和 `no-new-privileges`。
- 请求正文限制为 80 KB，文本限制为 20,000 字符。
- 页面设置了内容安全策略、禁止嵌入、禁用摄像头、麦克风与定位。
- 应用不记录用户提交的对话正文。

## 上云前仍需完成

Docker 只解决应用打包与运行。真正绑定公网域名时，还需要在服务器上完成：

1. 安装并更新 Docker。
2. 配置云防火墙或安全组，只开放 SSH、HTTP 和 HTTPS 所需端口。
3. 使用 Nginx 或 Caddy 反向代理容器，不直接公开容器端口。
4. 为域名签发 HTTPS 证书，并将 HTTP 自动跳转到 HTTPS。
5. 配置日志轮换、自动备份和服务可用性监控。
6. 根据服务器所在地区确认域名备案要求。

服务器地址、域名和证书路径尚未确定，因此本阶段不写死云厂商或域名配置。
