from json import dumps
from os import ilistdir, remove, sync
from machine import reset
from socket import getaddrinfo, socket, SOL_SOCKET, SO_REUSEADDR
from time import sleep

from .logging import CustomLogger

CSS_STYLE = b'''html {font-family: Arial}
table {width: 100%; border-collapse: collapse;}
th, td {border: 1px solid #ddd; padding: 8px; text-align: left;}
th {background-color: #f2f2f2;}'''

HTML_HOME = b'''<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><title>homebattery file manager</title>
<link rel="stylesheet" type="text/css" href="style.css"></head>
<body><h1>homebattery file manager</h1>
<table id="fileTable"><thead><tr><th>Filename</th><th>Action</th></tr></thead><tbody><!--files--></tbody></table><br>
<input type="file" id="fileInput"><button onclick="uploadFile()">Upload file</button><br><br><br>
<button onclick="resetDevice()">Reset device</button>
<script src="script.js"></script></body></html>'''

JS_HOME = b'''async function fetchFiles() {
    const response = await fetch('/list_files');
    const files = await response.json();
    const tableBody = document.getElementById('fileTable').getElementsByTagName('tbody')[0];
    tableBody.innerHTML = '';

    files.forEach(file => {
        const row = tableBody.insertRow();
        const cell1 = row.insertCell(0);
        const cell2 = row.insertCell(1);

        cell1.textContent = file;
        const deleteButton = document.createElement('button');
        deleteButton.textContent = 'Delete';
        deleteButton.onclick = () => deleteFile(file);
        cell2.appendChild(deleteButton);
    });
}

async function deleteFile(filename) {
    const url = `/delete/${encodeURIComponent(filename)}`;
    await fetch(url, {method: 'POST'});
    fetchFiles();
}

async function uploadFile() {
    const input = document.getElementById('fileInput');
    const file = input.files[0];
    const url = `/upload/${encodeURIComponent(file.name)}`;

    await fetch(url, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/octet-stream',
        },
        body: file,
    });
    input.value = '';
    fetchFiles();
}

async function resetDevice() {
    await fetch('/reset', {method: 'POST'});
}

fetchFiles();
'''

HEADER_200 = 'HTTP/1.0 200 OK\r\nContent-type: %s\r\n\r\n'
HEADER_200_EMPTY = b'HTTP/1.0 200 OK\r\nContent-Length: 0'
HEADER_400 = b'HTTP/1.0 400 Bad Request\r\nContent-Length: 0'
HEADER_404 = b'HTTP/1.0 404 Not Found\r\nContent-Length: 0'

class PayloadIncompleteError(Exception):
    pass

class Webserver:
    def __init__(self):
        from .singletons import Singletons
        self.__log: CustomLogger = Singletons.log.create_logger('webserver')

        addr = getaddrinfo('0.0.0.0', 80)[0][-1]
        self.__socket = socket()
        self.__socket.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
        self.__socket.bind(addr)
        self.__socket.listen(1)

    def run(self):
        while True:
            try:
                conn, addr = self.__socket.accept()
                self.__log.info('Client: ', addr)

                path, payload = self.__read_request(conn)

                if path == '/' or path == '/index.html':
                    self.__handle_get(conn, 'text/html', HTML_HOME)
                elif path == '/style.css':
                    self.__handle_get(conn, 'text/css', CSS_STYLE)
                elif path == '/script.js':
                    self.__handle_get(conn, 'text/javascript', JS_HOME)
                elif path == '/list_files':
                    self.__handle_get(conn, 'application/json', dumps(self.__get_files()).encode('utf-8'))
                elif path is not None and path.startswith('/delete/'):
                    self.__handle_file_delete(conn, path[8:])
                elif path is not None and payload is not None and path.startswith('/upload/'):
                    self.__handle_file_upload(conn, path[8:], payload)
                elif path == '/reset':
                        reset()
                else:
                    self.__log.error('Unknown request: ', path)
                    conn.send(HEADER_404)
            except PayloadIncompleteError:
                conn.send(HEADER_400)
            except Exception as e:
                self.__log.error('Cycle failed: ', e)
                self.__log.trace(e)
            finally:
                conn.close()

    def __read_request(self, connection):
        try:
            parts = connection.readline().decode('utf-8').split(' ')
            method = parts[0]
            path = parts[1].rstrip()
            self.__log.info('Request: ', method, ' ', path)
            if method == 'GET':
                _ = connection.recv(1024) # ignore further header content
                return path, None
            elif method == 'POST':
                length = 0
                while True:
                    line = connection.readline().decode('utf-8')
                    if line is None or len(line) == 0 or line == '\r\n':
                        break
                    parts = line.split(' ')
                    if parts[0] == 'Content-Length:':
                        length = int(parts[-1].rstrip())
                payload = None
                if length > 0:
                    payload = b''
                    for _ in range(10):
                        payload += connection.recv(length - len(payload))
                        if len(payload) == length:
                            break
                        sleep(1)
                    else:
                        self.__log.error('Incomplete payload, ', length, ' Bytes expected, ', len(payload), ' Bytes received.')
                        raise PayloadIncompleteError()
                return path, payload
            raise NotImplementedError()
        except Exception as e:
            self.__log.error('Request failed: ', e)
            self.__log.trace(e)
            return None, None

    def __handle_get(self, connection, type: str, payload: bytes):
        connection.send((HEADER_200 % type).encode('utf-8'))
        connection.send(payload)

    def __handle_file_delete(self, connection, name):
        try:
            self.__check_file_type(name)
            remove('/' + name)
            sync()
        except Exception:
            self.__log.error('Can not delete file ', name)
        finally:
            connection.send(HEADER_200_EMPTY)
        
    def __handle_file_upload(self, connection, name, payload):
        try:
            self.__check_file_type(name)
            with open('/' + name, 'wb') as f:
                f.write(payload)
            sync()
        except Exception:
            self.__log.error('Can not create file ', name)
        finally:
            connection.send(HEADER_200_EMPTY)

    def __get_files(self):
        files = list()
        for fileinfo in ilistdir('/'):
            if fileinfo[1] != 0x8000: # no regular file
                continue
            file = fileinfo[0]
            if file.endswith('.py') or file.endswith('.mpy'):
                continue
            files.append(file)
        return files
    
    def __check_file_type(self, file):
        if file.endswith('.py') or file.endswith('.mpy'):
            self.__log.error('Blocked modification of code: ', file)
            raise PermissionError()
