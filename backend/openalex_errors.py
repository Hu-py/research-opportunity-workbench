"""Safe diagnostics for academic API calls: never interpolate full URLs or keys."""
import httpx

def safe_openalex_error(exc, key_configured=False):
    if isinstance(exc, httpx.HTTPStatusError):
        code=exc.response.status_code
        if code==409:
            return "OpenAlex HTTP 409：可能已用完无 Key 试用额度；请在 Render 配置免费的 OPENALEX_API_KEY。"
        if code==429:
            return "OpenAlex HTTP 429：触发频率或预算限制；请稍后重试，并检查免费 API Key 的额度。"
        if code==401:
            return "OpenAlex HTTP 401：API Key 不正确或没有访问权限；请检查 Render 环境变量。"
        if code==403:
            return "OpenAlex HTTP 403：API Key 可能尚未通过邮箱激活，或没有访问权限。"
        if code>=500:
            return "OpenAlex HTTP "+str(code)+"：学术接口暂时不可用，请稍后重试。"
        return "OpenAlex HTTP "+str(code)+"：检索服务拒绝请求，请检查检索策略与认证。"
    if isinstance(exc,httpx.TimeoutException):
        return "OpenAlex 请求超时：请稍后重试。"
    if isinstance(exc,httpx.TransportError):
        return "OpenAlex 网络连接失败：Render 暂时无法连通学术检索服务。"
    if isinstance(exc,(ValueError,KeyError,TypeError)):
        return "OpenAlex 返回内容不符合预期，无法解析候选论文。"
    return "论文检索发生未分类错误："+type(exc).__name__+"；请联系管理员查看后端日志。"
