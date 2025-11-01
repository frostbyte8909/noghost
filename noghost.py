# basic imports needed for sockets and threads
import socket
import threading
import sys
import time

# ascii art greeting for noghost., defined as a raw string
def welcome_screen():
        print('''
    .___             __            .__                    __                    
  __│ _╱____   _____╱  │_     ____ │  │__   ____  _______╱  │_    _____   ____  
 ╱ __ │╱  _ ╲ ╱    ╲   __╲   ╱ ___╲│  │  ╲ ╱  _ ╲╱  ___╱╲   __╲  ╱     ╲_╱ __ ╲ 
╱ ╱_╱ (  <_> )   │  ╲  │    ╱ ╱_╱  >   Y  (  <_> )___ ╲  │  │   │  Y Y  ╲  ___╱ 
╲____ │╲____╱│___│  ╱__│    ╲___  ╱│___│  ╱╲____╱____  > │__│   │__│_│  ╱╲___  >
     ╲╱           ╲╱       ╱_____╱      ╲╱           ╲╱               ╲╱     ╲╱ 
         ''')

# variables for server: listen on all interfaces and use 12345 port
host = '0.0.0.0'
port = 12345
file_name = 'chat_messages.txt'
clients = []
clients_lock = threading.Lock()

# dependency: alive-progress for nice loading UI
try:
    from alive_progress import alive_bar
except Exception:
    # Print very simple, copy-paste install commands per OS and exit
    print('\nMissing dependency: alive-progress')
    if sys.platform.startswith('win'):
        print('Install with (copy & paste into your Windows terminal):')
        print('py -3 -m pip install alive-progress')
        print('or')
        print('pip install alive-progress')
    else:
        print('Install with (copy & paste into your terminal):')
        print('python3 -m pip install alive-progress')
        print('or')
        print('pip3 install alive-progress')
    print('\nAfter installing, re-run this script.')
    sys.exit(1)

# helper: broadcast a bytes message to all clients (thread-safe)
def broadcast(data_bytes):
    with clients_lock:
        for c in clients[:]:
            try:
                c.sendall(data_bytes)
            except Exception:
                try:
                    c.close()
                except Exception:
                    pass
                try:
                    clients.remove(c)
                except ValueError:
                    pass

# handle individual connections (server side)
def handle_client(conn, addr):
    print('client from', addr, 'joined')
    try:
        with conn:
            while True:
                data = conn.recv(1024)
                if not data:
                    break
                msg = data.decode('utf-8')
                print(msg)
                # save message to file
                try:
                    with open(file_name, 'a') as f:
                        f.write(msg + '\n')
                except Exception as e:
                    print('failed to write message to file:', e)
                # send received message to all clients (including sender)
                with clients_lock:
                    for c in clients[:]:
                        try:
                            c.sendall(data)
                        except Exception:
                            try:
                                c.close()
                            except Exception:
                                pass
                            try:
                                clients.remove(c)
                            except ValueError:
                                pass
    except Exception as e:
        print('connection handler error for', addr, e)
    finally:
        with clients_lock:
            if conn in clients:
                clients.remove(conn)

# function to run server
def run_server():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        # allow quick restart of the server on the same port
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind((host, port))
        s.listen()
        print('server is listening on', port)
        # thread to read host input and broadcast as host (palash)
        def host_sender():
            # host will identify by OS name
            if sys.platform == 'darwin':
                host_name = 'macOS'
            elif sys.platform.startswith('win'):
                host_name = 'Windows'
            elif sys.platform.startswith('linux'):
                host_name = 'Linux'
            else:
                host_name = sys.platform
            try:
                while True:
                    line = input()
                    if not line:
                        continue
                    msg = f"{host_name}: {line}".encode('utf-8')
                    # save and broadcast
                    try:
                        with open(file_name, 'a') as f:
                            f.write(msg.decode('utf-8') + '\n')
                    except Exception:
                        pass
                    broadcast(msg)
            except (EOFError, KeyboardInterrupt):
                return

        threading.Thread(target=host_sender, daemon=True).start()
        while True:
            conn, addr = s.accept()
            # send initial connection message + 2s loading bar to the new client
            try:
                conn.sendall(b"Remote Link Established, Connecting Now\n")
                # show a 2-second loading bar on server and stream progress frames to client
                steps = 20
                step_sleep = 2.0 / steps
                with alive_bar(steps, title='Connecting') as bar:
                    for i in range(steps):
                        # send a simple frame to client
                        try:
                            frame = ('[' + ('=' * (i * 6 // steps)).ljust(6) + ']')
                            conn.sendall((frame + '\r').encode('utf-8'))
                        except Exception:
                            pass
                        time.sleep(step_sleep)
                        bar()
                conn.sendall(b"\nConnection ready.\n")
            except Exception:
                pass
            with clients_lock:
                clients.append(conn)
            threading.Thread(target=handle_client, args=(conn, addr), daemon=True).start()

# function for client to connect and chat
def run_client(server_ip):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.connect((server_ip, port))
        print('connected to', server_ip, 'on port', port)
        # receive messages from server on separate thread
        def reader():
            try:
                while True:
                    data = s.recv(1024)
                    if not data:
                        break
                    # print with separators for readability
                    text = data.decode('utf-8')
                    print('\n' + '-'*40)
                    print(text)
                    print('-'*40 + '\n')
            except Exception as e:
                print('reader error', e)
        threading.Thread(target=reader, daemon=True).start()

        # choose username as OS name
        if sys.platform.startswith('win'):
            username = 'Windows'
        elif sys.platform == 'darwin':
            username = 'macOS'
        elif sys.platform.startswith('linux'):
            username = 'Linux'
        else:
            username = sys.platform

        while True:
            try:
                msg = input(f"{username}: ")
            except (EOFError, KeyboardInterrupt):
                break
            if msg.lower() == 'exit':
                break
            s.sendall(f'{username}: {msg}'.encode('utf-8'))

# main entry
if __name__ == '__main__':
    welcome_screen()
    # check args and start accordingly
    if len(sys.argv) < 2:
        print('usage: python noghost.py server|client [server_ip]')
        sys.exit(1)
    role = sys.argv[1].lower()
    if role == 'server':
        run_server()
    elif role == 'client':
        if len(sys.argv) < 3:
            print('need server ip for client mode')
            sys.exit(1)
        run_client(sys.argv[2])
    else:
        print('unknown role. use server or client')
