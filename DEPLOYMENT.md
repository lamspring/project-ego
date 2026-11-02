# EGO-A 部署

## 通用要求

- Python 3.11+；核心运行时只使用标准库。
- 标准 Node.js 与 DSH，准备名为 `ego-a` 的 DSH profile。
- 可选：官方 `lark-cli`（飞书）与 Obsidian CLI（可读知识层）。
- `DEEPSEEK_API_KEY` 只放在服务环境中，不写入仓库或 `config/local.json`。

```bash
python3 -m unittest discover -s tests -v
export DEEPSEEK_API_KEY='...'
python3 dsh_ego_launcher.py '你好'
```

## 飞书配置

```bash
export FEISHU_APP_ID='...'
export FEISHU_APP_SECRET='...'
python3 dsh_feishu_setup.py
```

只在初始化时设置 App Secret。随后从 `config/local.example.json` 复制 `config/local.json`，填写主人 open ID 和私聊 chat ID；也可以使用同名环境变量。`config/local.json` 已被 `.gitignore` 排除。

## Linux 手动运行

```bash
python3 dsh_service_control.py start
python3 dsh_service_control.py status
python3 dsh_service_control.py stop
```

Linux 的 Worker 和异步命令通过独立 session/process group 运行；Windows 使用 `Win32_Process.Create`，避免 Agent shell 退出时回收后台进程。

## Linux systemd

1. 将项目放在 `/opt/project-ego`，创建 `/etc/ego-a/ego-a.env`，参考 `deploy/ego-a.env.example`。
2. 根据实际安装位置调整 `deploy/ego-a.service` 中的路径。
3. 安装并启动服务：

```bash
sudo cp deploy/ego-a.service /etc/systemd/system/ego-a.service
sudo systemctl daemon-reload
sudo systemctl enable --now ego-a
sudo systemctl status ego-a
```

`danger-full-access` 是主人明确选择的开放运行模式，不代表外部事件获得无限授权；人工停止、重大外部行动审批和审计仍是 EGO 作业规则。生产环境应使用专用操作系统账号并限制该账号实际能访问的资源。

## 不发布的内容

`ego.db`、审计数据库、Session、凭据、主人渠道 ID、飞书消息、Worker 日志、异步输出和 `config/local.json` 都属于本机运行状态，不得提交到公开仓库。
