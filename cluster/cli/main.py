import argparse
from cluster.daemon.service import DaemonService


def main():
    parser = argparse.ArgumentParser(description="Clusnux node agent")
    parser.add_argument("--host", default="0.0.0.0", help="Bind host")
    parser.add_argument("--port", type=int, default=8734, help="WebSocket port")
    args = parser.parse_args()

    daemon = DaemonService(host=args.host, port=args.port)
    daemon.start()
    daemon.join()


if __name__ == "__main__":
    main()

