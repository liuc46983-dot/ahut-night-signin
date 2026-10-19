# Render 部署

1. 在自己的 GitHub 新建仓库，上传本目录源文件（不要上传 .env、账号密码、缓存或虚拟环境）。render.yaml 必须在仓库根目录。
2. 打开 https://dashboard.render.com/ ，登录并连接该 GitHub 仓库。
3. 选择 New → Blueprint，选择仓库。确认方案为 Free 后部署，配置来自 render.yaml。
4. 等待 Live，打开平台分配的实际 HTTPS 网址；先检查 /api/health，再用手机确认主页可打开。
5. 应用自动读取 Render 的 RENDER_EXTERNAL_URL 校验提交来源，无需手填网址。以后绑定自定义域名时，将 SITE_ORIGIN 设置为该 HTTPS 源站地址（不带路径）。

免费实例空闲后会休眠，再次访问需要等待唤醒。不能保证在所有网络可访问；发布成功后仍须在实际手机网络验证。尚未使用真实学校账号验证签到。

说明：https://render.com/docs/free 、https://render.com/docs/blueprint-spec


## 来源

签到核心来自 https://github.com/UnthinkingBrain/-_ahut_wqqd ，提交 c3c98af98ea57c7f7a02cff3b8a65eabd7553eb8。保留原作者署名。原 README 声明 MIT，原版本未包含独立 LICENSE。网页仅支持本人账号手动操作；使用学校接口返回的宿舍坐标，并非手机实时 GPS。真实签到结果需以学校系统记录为准。密码不持久化，核心日志关闭。
