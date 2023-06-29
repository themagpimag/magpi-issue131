# Multithreaded Neopixel animations and web server to run on a Raspberry Pi
# PICO W and Micropython 1.19.1 or newer.
#
import utime, array
from machine import Pin
import rp2
import random
import socket
import network
import _thread
from secrets import secrets


# Configure the number of WS2812 LEDs, pins and brightness.
NUM_LEDS = 8
PIN_NUM = 22
brightness = 0.5
 
 
@rp2.asm_pio(sideset_init=rp2.PIO.OUT_LOW, out_shiftdir=rp2.PIO.SHIFT_LEFT, autopull=True, pull_thresh=24)
def ws2812():
    T1 = 2
    T2 = 5
    T3 = 3
    wrap_target()
    label("bitloop")
    out(x, 1)               .side(0)    [T3 - 1]
    jmp(not_x, "do_zero")   .side(1)    [T1 - 1]
    jmp("bitloop")          .side(1)    [T2 - 1]
    label("do_zero")
    nop()                   .side(0)    [T2 - 1]
    wrap()
 
 
# Create the StateMachine with the ws2812 program, outputting on Pin(22).
sm = rp2.StateMachine(0, ws2812, freq=8_000_000, sideset_base=Pin(PIN_NUM))
sm.active(1)
ar = array.array("I", [0 for _ in range(NUM_LEDS)])
 
def pixels_show():
    dimmer_ar = array.array("I", [0 for _ in range(NUM_LEDS)])
    for i,c in enumerate(ar):
        r = int(((c >> 8) & 0xFF) * brightness)
        g = int(((c >> 16) & 0xFF) * brightness)
        b = int((c & 0xFF) * brightness)
        dimmer_ar[i] = (g<<16) + (r<<8) + b
    sm.put(dimmer_ar, 8)
    utime.sleep_ms(10)
 
def pixels_set(i, color):
    ar[i] = (color[1]<<16) + (color[0]<<8) + color[2]
    
def pixel_group_set(pg, color):
    for i in range(len(pg)):
        pixels_set(pg[i], color)
 
def pixels_fill(color):
    for i in range(len(ar)):
        pixels_set(i, color)
 
BLACK = (0, 0, 0)
RED = (255, 0, 0)
ORANGE = (255, 165, 0)
YELLOW = (255, 255, 0)
GREEN = (0, 255, 0)
CYAN = (0, 255, 255)
BLUE = (0, 0, 255)
PURPLE = (255, 0, 255)
WHITE = (255, 255, 255)
STANDARD = (200, 200, 200)
COLORS = (RED, ORANGE, YELLOW, GREEN, CYAN, BLUE, PURPLE, WHITE, STANDARD)

#pixels_fill(WHITE)

rgb_offset = (256/NUM_LEDS)

#####################################################
#Pixel Groups
ALL = [0,1,2,3,4,5,6,7,8,9,10,11,
           12,13,14,15,16,17,18,19,20,21,22,23,
           24,25,26,27,28,29,30,31,32,33,34,35,
           36]
LR = [0,1,2,3,4,5,6,7,8]
LF = [17,16,15,14,13,12,11,10,9]
RR = [36,35,34,33,32,31,30,29,28]
RF = [19,20,21,22,23,24,25,26,27]
HEADLIGHTS = [14,15,16,17,18,19,20,21,22,23]
BRAKES = [0,1,2,3,4,5,36,35,34,33,32,31]

#####################################################
# Animations
def chase():
    color = COLORS[random.randint(0,len(COLORS)-1)]
    for i in range(0,NUM_LEDS):
        pixels_set(ALL[i], color)
        pixels_show()
        utime.sleep(.02)

def randomSet():
    color = COLORS[random.randint(0,len(COLORS)-1)]
    pixel = ALL[random.randint(0,len(ALL)-1)]
    pixels_set(pixel, color)
    pixels_show()
    utime.sleep(0.2)

def default_lights():
    pixels_fill(WHITE)

def purple_lights():
    pixels_fill(PURPLE)
    utime.sleep(120)
    pixels_fill(WHITE)
    
def red_lights():
    pixels_fill(RED)
    utime.sleep(120)
    pixels_fill(WHITE)
        
def blue_lights():
    pixels_fill(BLUE)
    utime.sleep(120)
    pixels_fill(WHITE)

def rainbow():
    for i in range (0,1000):
        for rgb in range(0, 255, 4):
            for led in range(0, NUM_LEDS):
                colour = ((rgb + (led * rgb_offset)), 255, 255)
                pixels_set(led, colour)
            sleep(0.01)

def subscribe():
    for i in range (0,9):
        pixels_fill(PURPLE)
        utime.sleep(0.5)
        pixels_fill(RED)
        utime.sleep(0.5)
    pixels_fill(WHITE)
    
def raid():
    loop = 1
    for i in range (0,29):
        for j in range (NUM_LEDS):
            if (i+j) <= NUM_LEDS:
                if loop == 1:
                    pixels_set((i+j), ORANGE)
                    loop = 2
                if loop == 2:
                    pixels_set((i+j), BLUE)
                    loop = 3
                if loop == 3:
                    pixels_set((i+j), WHITE)
                    loop = 1
            else:
                if loop == 1:
                    pixels_set(((i+j)-NUM_LEDS), ORANGE)
                    loop = 2
                if loop == 2:
                    pixels_set((i+j)-NUM_LEDS), BLUE
                    loop = 3
                if loop == 3:
                    pixels_set(((i+j)-NUM_LEDS), WHITE)
                    loop = 1
            utime.sleep(0.5)
    
# Shared variable between two threads
ANIMATION = ""
LASTREQUEST = 0
    
#####################################################
# Set Up Webserver Thread

def ws_thread(s):
    global ANIMATION
    global LASTREQUEST
    
    print('Starting second thread for the webserver answer loop')
    
    html = """<!DOCTYPE html>
    <html>
        <head> <title>Stream lights</title>
        <body> <h1>On Pico W</h1>
        <p>%s</p>
    </body>
    </html>


    """
    # Listen for connections
    while True:
        try:
            cl, addr = s.accept()
            print('client connected from', addr)
            
            cl.settimeout(1.0) #keep iphone from holding open a connection
            request = cl.recv(1024)
            request = str(request)
            
            purple_redeem = request.find('?purple ')
            if purple_redeem >= 0:
                ANIMATION = 'purple'
            
            red_redeem = request.find('?red ')
            if red_redeem >= 0:
                ANIMATION = 'red'
                
            blue_redeem = request.find('?blue ')
            if blue_redeem >= 0:
                ANIMATION = 'blue'
                
            rainbow_redeem = request.find('?rainbow ')
            if rainbow_redeem >= 0:
                ANIMATION = 'rainbow'
            
            subscription = request.find('?subscription ')
            if subscription >= 0:
                ANIMATION = 'subscription'
            
            channel_raid = request.find('?raid ')
            if channel_raid >= 0:
                ANIMATION = 'channel_raid'
            
            cancel = request.find('?cancel ')
            if cancel >= 0:
                ANIMATION = ''
                LASTREQUEST = 0
                
            print("Client requested :",ANIMATION)
            
            if ANIMATION != '':
                LASTREQUEST = int(utime.time())

            response = html

            cl.send('HTTP/1.0 200 OK\r\nContent-type: text/html\r\n\r\n')
            cl.send(response)
            cl.close()
            print('connection closed')
            
        except OSError as e:
            cl.close()
            print('connection closed on error')

#Start the web server

wlan = network.WLAN(network.STA_IF)
wlan.active(True)
wlan.connect(secrets['ssid'], secrets['pass'])

max_wait = 10
while max_wait > 0:
    if wlan.status() < 0 or wlan.status() >= 3:
        break
    max_wait -= 1
    print('waiting for connection...')
    utime.sleep(1)

if wlan.status() != 3:
    raise RuntimeError('network connection failed')
else:
    print('connected')
    status = wlan.ifconfig()
    print( 'ip = ' + status[0] )

addr = socket.getaddrinfo('0.0.0.0', 80)[0][-1]

s = socket.socket()
s.bind(addr)
s.listen(1)

print('listening on', addr)

def animThread():
    global ANIMATION
    global LASTREQUEST
    print('Starting main animation thread')
    while True:
        if ANIMATION == "purple":
            purple_lights()
        elif ANIMATION == "red":
            red_lights()
        elif ANIMATION == "blue":
            blue_lights()
        elif ANIMATION == "rainbow":
            rainbow()
        elif ANIMATION == "subscription":
            brakes()
        elif ANIMATION == "raid":
            raid()
        else:
            default_lights()
        
        #Check to see if the last command was more than 30 seconds ago
        if LASTREQUEST != 0:
            timeout = int(utime.time() - LASTREQUEST)
            if timeout > 30:
                print("Animation Timed out, resetting.")
                default_lights()

#####################################################
# Start the animation loop on the second RP2040 core
second_thread = _thread.start_new_thread(animThread, ())

#####################################################
# Start the main thread Loop for the web service
ws_thread(s)
    


