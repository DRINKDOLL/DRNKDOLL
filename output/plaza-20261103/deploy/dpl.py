#!/usr/bin/env python3
"""远程操作工具：ssh exec / upload / download。
凭据从环境变量读取，绝不写入命令行或日志。
"""
import os
import sys
import stat
import time
import paramiko

HOST = os.environ.get("DPL_HOST", "")
PORT = int(os.environ.get("DPL_PORT", "22"))
USER = os.environ.get("DPL_USER", "")
PWD = os.environ.get("DPL_PASS", "")


def connect(retries=3):
    last = None
    for i in range(retries):
        try:
            c = paramiko.SSHClient()
            c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            c.connect(
                HOST, port=PORT, username=USER, password=PWD,
                timeout=20, banner_timeout=30, auth_timeout=30,
                look_for_keys=False, allow_agent=False,
            )
            return c
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(2)
    raise SystemExit(f"SSH connect failed: {last}")


def main():
    if len(sys.argv) < 2:
        raise SystemExit("usage: dpl.py exec '<cmd>' | put <local> <remote> | get <remote> <local>")
    mode = sys.argv[1]
    c = connect()
    try:
        if mode == "exec":
            cmd = sys.argv[2]
            stdin, stdout, stderr = c.exec_command(cmd, timeout=1800, get_pty=False)
            out = stdout.read().decode("utf-8", "replace")
            err = stderr.read().decode("utf-8", "replace")
            rc = stdout.channel.recv_exit_status()
            if out:
                sys.stdout.write(out)
            if err:
                sys.stdout.write("--- stderr ---\n" + err)
            sys.exit(rc)

        elif mode == "put":
            local, remote = sys.argv[2], sys.argv[3]
            sftp = c.open_sftp()
            size = os.path.getsize(local)
            state = {"pct": -1}

            def cb(done, total):
                pct = int(done * 100 / total) if total else 0
                if pct // 10 != state["pct"] // 10:
                    state["pct"] = pct
                    print(f"  {pct}%  {done/1048576:.0f}/{total/1048576:.0f} MB", flush=True)

            sftp.put(local, remote, callback=cb)
            print(f"uploaded {local} -> {remote} ({size} bytes)")
            sftp.close()

        elif mode == "putdir":
            local, remote = sys.argv[2], sys.argv[3]
            sftp = c.open_sftp()
            n = 0
            total = 0
            for root, dirs, files in os.walk(local):
                rel = os.path.relpath(root, local).replace("\\", "/")
                rdir = remote if rel == "." else f"{remote}/{rel}"
                try:
                    sftp.stat(rdir)
                except IOError:
                    sftp.mkdir(rdir)
                for f in files:
                    lp = os.path.join(root, f)
                    rp = f"{rdir}/{f}"
                    sftp.put(lp, rp)
                    n += 1
                    total += os.path.getsize(lp)
            print(f"uploaded {n} files, {total/1048576:.1f} MB -> {remote}")
            sftp.close()

        elif mode == "push":
            # 流式推送：本地文件 -> 远端命令 stdin（如 tar xzf - -C /opt/plaza）
            local, remote_cmd = sys.argv[2], sys.argv[3]
            size = os.path.getsize(local)
            stdin, stdout, stderr = c.exec_command(remote_cmd, timeout=3600)
            sent = 0
            last = -1
            with open(local, "rb") as f:
                while True:
                    chunk = f.read(262144)
                    if not chunk:
                        break
                    stdin.write(chunk)
                    sent += len(chunk)
                    pct = int(sent * 100 / size)
                    if pct // 10 != last // 10:
                        last = pct
                        print(f"  {pct}%  {sent/1048576:.0f}/{size/1048576:.0f} MB", flush=True)
            stdin.flush()
            stdin.channel.shutdown_write()
            out = stdout.read().decode("utf-8", "replace")
            err = stderr.read().decode("utf-8", "replace")
            rc = stdout.channel.recv_exit_status()
            if out:
                sys.stdout.write(out)
            if err:
                sys.stdout.write("--- stderr ---\n" + err)
            print(f"push done: {sent} bytes, rc={rc}")
            sys.exit(rc)

        elif mode == "get":
            remote, local = sys.argv[2], sys.argv[3]
            sftp = c.open_sftp()
            sftp.get(remote, local)
            print(f"downloaded {remote} -> {local}")
            sftp.close()

        else:
            raise SystemExit("unknown mode")
    finally:
        c.close()


if __name__ == "__main__":
    main()
