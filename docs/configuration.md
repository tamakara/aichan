# 配置管理

本项目不再使用环境变量作为运行配置来源。

## 规则

- 每个服务只读取自身目录内的 `config.yml`。
- 代码不会读取 `.env`、`.env.example` 或环境变量别名。
- 修改接口地址、端口、超时等参数时，只更新对应服务的 `config.yml`。

## 文件位置

- `agent-service/config.yml`
- `hub-service/config.yml`
- `qq-adapter-service/config.yml`

## Docker Compose

`docker-compose.yml` 通过只读挂载将这三份配置文件映射到容器内，容器与本地运行共享同一配置语义。
