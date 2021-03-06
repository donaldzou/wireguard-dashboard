import os
from flask import Flask, request, render_template, redirect, url_for
import subprocess
from datetime import datetime, date, time, timedelta
from tinydb import TinyDB, Query
import time
import requests


conf_location = "/etc/wireguard"

app = Flask("Wireguard Dashboard")
app.config['TEMPLATES_AUTO_RELOAD'] = True
css = ""
conf_data = {}


def get_conf_peer_key(config_name):
    keys = []
    try: peer_key = subprocess.check_output("wg show "+config_name+" peers", shell=True)
    except Exception: return "stopped"
    peer_key = peer_key.decode("UTF-8").split()
    for i in peer_key: keys.append(i)
    return keys


def get_conf_running_peer_number(config_name):
    running = 0
    #Get latest handshakes
    try: data_usage = subprocess.check_output("wg show "+config_name+" latest-handshakes", shell=True)
    except Exception: return "stopped"
    data_usage = data_usage.decode("UTF-8").split()
    count = 0
    now = datetime.now()
    b = timedelta(minutes=2)
    for i in range(int(len(data_usage)/2)):
        minus = now - datetime.fromtimestamp(int(data_usage[count+1]))
        if minus < b:
            running += 1
        count += 2
    return running

def get_conf_peers_data(config_name):
    peer_data = {}
    # Get key
    try: peer_key = subprocess.check_output("wg show "+config_name+" peers", shell=True)
    except Exception: return "stopped"
    peer_key = peer_key.decode("UTF-8").split()
    for i in peer_key: peer_data[i] = {}

    #Get transfer
    try: data_usage = subprocess.check_output("wg show "+config_name+" transfer", shell=True)
    except Exception: return "stopped"
    data_usage = data_usage.decode("UTF-8").split()
    count = 0
    upload_total = 0
    download_total = 0
    total = 0
    for i in range(int(len(data_usage)/3)):
        peer_data[data_usage[count]]['total_recive'] = round(int(data_usage[count+1])/(1024**3),4)
        peer_data[data_usage[count]]['total_sent'] = round(int(data_usage[count+2])/(1024**3),4)
        peer_data[data_usage[count]]['total_data'] = round((int(data_usage[count+2])+int(data_usage[count+1]))/(1024**3),4)
        count += 3

    #Get endpoint
    try: data_usage = subprocess.check_output("wg show "+config_name+" endpoints", shell=True)
    except Exception: return "stopped"
    data_usage = data_usage.decode("UTF-8").split()
    count = 0
    for i in range(int(len(data_usage)/2)):
        peer_data[data_usage[count]]['endpoint'] = data_usage[count+1]
        count += 2

    #Get latest handshakes
    try: data_usage = subprocess.check_output("wg show "+config_name+" latest-handshakes", shell=True)
    except Exception: return "stopped"
    data_usage = data_usage.decode("UTF-8").split()
    count = 0
    now = datetime.now()
    b = timedelta(minutes=2)
    for i in range(int(len(data_usage)/2)):
        minus = now - datetime.fromtimestamp(int(data_usage[count+1]))
        if minus < b:
            peer_data[data_usage[count]]['status'] = "running"
        else:
            peer_data[data_usage[count]]['status'] = "stopped"
        peer_data[data_usage[count]]['latest_handshake'] = minus
        count += 2
    
    #Get allowed ip
    try: data_usage = subprocess.check_output("wg show "+config_name+" allowed-ips", shell=True)
    except Exception: return "stopped"
    data_usage = data_usage.decode("UTF-8").split()
    count = 0
    for i in range(int(len(data_usage)/2)):
        peer_data[data_usage[count]]['allowed_ip'] = data_usage[count+1]
        count += 2

    return peer_data




def get_conf_pub_key(config_name):
    try: pub_key = subprocess.check_output("wg show "+config_name+" public-key", shell=True)
    except Exception: return "stopped"
    return pub_key.decode("UTF-8")

def get_conf_listen_port(config_name):
    try: pub_key = subprocess.check_output("wg show "+config_name+" listen-port", shell=True)
    except Exception: return "stopped"
    return pub_key.decode("UTF-8")
    

def get_conf_total_data(config_name):
    try: data_usage = subprocess.check_output("wg show "+config_name+" transfer", shell=True)
    except Exception: return "stopped"
    data_usage = data_usage.decode("UTF-8").split()
    count = 0
    upload_total = 0
    download_total = 0
    total = 0
    for i in range(int(len(data_usage)/3)):
        upload_total += int(data_usage[count+1])
        download_total += int(data_usage[count+2])
        count += 3
    
    total = round(((((upload_total+download_total)/1024)/1024)/1024),4)
    upload_total = round(((((upload_total)/1024)/1024)/1024),4)
    download_total = round(((((download_total)/1024)/1024)/1024),4)
    
    return [total, upload_total, download_total]


def get_conf_status(config_name):
    try: status = subprocess.check_output("wg show "+config_name, shell=True)
    except Exception: return "stopped"
    else: return "running" 


def get_conf_list():
    conf = []
    for i in os.listdir(conf_location):
        if ".conf" in i:
            i = i.replace('.conf','')
            temp = {"conf":i, "status":get_conf_status(i), "public_key": get_conf_pub_key(i)}
            if temp['status'] == "running":
                temp['checked'] = 'checked'
            else: temp['checked'] = "" 
            conf.append(temp)
    return conf

@app.route('/',methods=['GET'])
def index():
    return render_template('index.html', conf=get_conf_list())


@app.route('/configuration/<config_name>', methods=['GET'])
def conf(config_name):
    conf_data = {
        "name": config_name,
        "status": get_conf_status(config_name),
        "total_data_usage": get_conf_total_data(config_name),
        "public_key": get_conf_pub_key(config_name),
        "listen_port": get_conf_listen_port(config_name),
        "peer_data":get_conf_peers_data(config_name),
        "running_peer": get_conf_running_peer_number(config_name),
        "checked": ""
    }
    if conf_data['status'] == "stopped":
        print(conf_data)
        return redirect('/')
    else:
        conf_data['checked'] = "checked"
        return render_template('configuration.html', conf=get_conf_list(), conf_data=conf_data)


@app.route('/switch/<config_name>', methods=['GET'])
def switch(config_name):
    status = get_conf_status(config_name)
    if status == "running":
        try: status = subprocess.check_output("wg-quick down "+config_name, shell=True)
        except Exception: return redirect('/')
    elif status == "stopped":
        try: status = subprocess.check_output("wg-quick up "+config_name, shell=True)
        except Exception: return redirect('/')
    return redirect('/')


@app.route('/add_peer/<config_name>', methods=['POST'])
def add_peer(config_name):
    data = request.get_json()
    public_key = data['public_key']
    allowed_ips = data['allowed_ips']
    keys = get_conf_peer_key(config_name)
    if public_key in keys:
        return "Key already exist."
    else:
        status = ""
        try: 
            status = subprocess.check_output("wg set "+config_name+" peer "+public_key+" allowed-ips "+allowed_ips, shell=True, stderr=subprocess.STDOUT)
            status = subprocess.check_output("wg-quick save "+config_name, shell=True, stderr=subprocess.STDOUT)
            return "true"
        except subprocess.CalledProcessError as exc:
            return exc.output.strip()

            # return redirect('/configuration/'+config_name)

@app.route('/remove_peer/<config_name>', methods=['POST'])
def remove_peer(config_name):
    data = request.get_json()
    delete_key = data['peer_id']
    keys = get_conf_peer_key(config_name)
    if delete_key not in keys:
        return "This key does not exist"
    else:
        try:
            status = subprocess.check_output("wg set "+config_name+" peer "+delete_key+" remove", shell=True, stderr=subprocess.STDOUT)
            status = subprocess.check_output("wg-quick save "+config_name, shell=True, stderr=subprocess.STDOUT)
            return "true"
        except subprocess.CalledProcessError as exc:
            return exc.output.strip()

app.run(host='0.0.0.0',debug=False, port=10086)