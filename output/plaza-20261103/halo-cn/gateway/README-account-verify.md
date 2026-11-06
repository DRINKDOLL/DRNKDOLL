# 账号确认接口对接 · 联调说明

模块：`gateway/account_verify.py`，封装广场调用警院论坛「账号确认接口」的完整接口层逻辑。

## 一、接口

```
POST http://8.138.246.181/answer/api/v1/account/verify
```

用户用警院论坛账号登录广场时，广场 BFF 用自身 AppKey `jy-plaza-svc` + L2 签名调用该接口，经统一网关转发到论坛做**只读账号确认**，返回 `data.confirmed` 与最小身份信息。

## 二、环境变量（必读）

| 变量 | 必填 | 说明 |
| --- | --- | --- |
| `PLAZA_APP_SECRET` | 是* | 广场 AppSecret；缺失时回退读本地 `configs/secrets.json` |
| `PLAZA_APP_KEY` | 否 | 广场 AppKey，默认 `jy-plaza-svc` |
| `JY_GATEWAY_BASE` | 否 | 网关地址，默认 `http://8.138.246.181` |

\* 密钥读取优先级：**环境变量 `PLAZA_APP_SECRET` > 本地 `gateway/configs/secrets.json`**。生产环境建议只用环境变量；`secrets.json` 已加入 `.gitignore`，禁止提交。

## 三、快速联调（CLI）

```bash
export PLAZA_APP_SECRET="<真实密钥>"
cd halo-cn
python -m gateway.account_verify <账号> <密码> [AppKey]
# 例：
python -m gateway.account_verify admin@jspi.edu.cn Admin@12345
```

退出码：`0` 表示确认成功、可建立会话；`1` 表示拒绝登录或调用失败。

## 四、库函数调用

```python
from gateway.account_verify import verify_account

r = verify_account("admin@jspi.edu.cn", "Admin@12345")  # app_key 默认 jy-plaza-svc
if r.confirmed:
    # 建立本平台会话（当前为占位，接入 Halo 登录时实现）
    create_platform_session(user_id=r.user_id, username=r.username, role=r.role)
else:
    # 统一提示「账号或密码错误」，不区分原因（防枚举）
    ...
```

## 五、安全红线

- AppSecret 只经环境变量注入，不硬编码、不写日志；
- 密码仅本进程调用期间短暂存在，不落盘、不写日志、不入会话、不缓存；
- 只判断 `r.confirmed` 作为登录结论，不依赖 `r.reason` 做业务分流；
- 账号不存在与密码错误返回同一结论（`invalid_credentials`），广场侧统一提示。

## 六、验证结果

- 离线自测：签名头生成与 `build_canonical` 复算一致、成功/失败包络解析正确、缺密钥拦截生效 —— 全部通过。
- 真实密钥正向联调（`jy-plaza-svc`）：A 组成功用例（邮箱/用户名/显式 login_type）全部 `confirmed=True`、角色 `admin`、邮箱掩码 `a***@jspi.edu.cn`；B 组失败用例（密码错误/账号不存在/缺参/非法 login_type）返回码与论坛侧验收脚本一致，防枚举生效。
- 密钥已落地：环境变量注入 + `gateway/configs/secrets.json` 兜底（已加入 `.gitignore`）。
- 待办：接入 Halo 登录流程，实现 `create_platform_session`（建立广场会话）。
