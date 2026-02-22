from pythonosc.dispatcher import Dispatcher
from pythonosc.osc_server import ThreadingOSCUDPServer

def handler(addr, *args):
    print("RECV", addr, args)

disp = Dispatcher()
disp.set_default_handler(handler)

server = ThreadingOSCUDPServer(("127.0.0.1", 9000), disp)
print("Listening on", server.server_address)
server.serve_forever()