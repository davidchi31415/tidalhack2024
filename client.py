import socket

SERVER_IP = ''
SERVER_PORT = 3001

s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
# s.connect(("127.0.0.1", SERVER_PORT))

s.bind((SERVER_IP, SERVER_PORT))
s.listen(5)
print('Server is now running.')

while True:
    client_socket, address = s.accept()
    print(f"Connection from {address} has been established.")
    client_socket.send(b"testing")