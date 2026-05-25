import sys
import os
import argparse
import threading


def main():
    parser = argparse.ArgumentParser(description="SmartDB MCP - 智能数据库查询助手")
    parser.add_argument("--web", action="store_true", help="仅启动Web管理后台（不启动MCP服务）")
    parser.add_argument("--no-web", action="store_true", help="MCP模式下不启动Web管理后台")
    parser.add_argument("--port", type=int, default=8765, help="Web管理后台端口 (默认8765)")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="Web管理后台监听地址 (默认127.0.0.1)")
    args = parser.parse_args()

    if args.web:
        _run_web(args.host, args.port)
    else:
        if args.no_web:
            _run_mcp()
        else:
            _run_mcp_with_web(args.host, args.port)


def _run_mcp():
    from mcp_server import mcp
    mcp.run(transport="stdio")


def _run_web(host, port):
    import uvicorn
    from main import app
    print(f"问数MCP管理后台已启动: http://{host}:{port}")
    print("在浏览器中打开上述地址即可管理数据库配置")
    uvicorn.run(app, host=host, port=port)


def _run_mcp_with_web(host, port):
    from mcp_server import mcp
    import uvicorn
    from main import app

    web_thread = threading.Thread(
        target=uvicorn.run,
        args=(app,),
        kwargs={"host": host, "port": port, "log_level": "warning"},
        daemon=True,
    )
    web_thread.start()
    print(f"问数MCP管理后台已启动: http://{host}:{port}", file=sys.stderr)

    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
