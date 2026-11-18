#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
DNS Protector topo demonstarcyjne 
 
Floodlight 1.2 controller
        |
        |       
H1 --- S1 (Open VSW) ---- H3(dnsmasq, server DNS)
.1      |                   10.0.0.3
        |
        |--nat0 eth0 VM -- Internet
            10.0.0.254 

Jeden Switch podłaczony do floodlight, hosta klienckiego i serwera DNS.
SW posiadający wyjście do internetu
 

"""
 
import sys
import os
from mininet.topo import Topo
from mininet.net import Mininet
from mininet.node import RemoteController, OVSSwitch
from mininet.cli import CLI
from mininet.log import setLogLevel, info

DNS_IP = '10.0.0.3'
GW_IP = '10.0.0.254'
UPSTREAM_DNS = ['8.8.8.8', '1.1.1.1']
RESOLV = '/etc/resolv.conf'


class DnsProtectorTopo(Topo):

    def build(self):
        s1 = self.addSwitch('s1')

        h1 = self.addHost('h1', ip='10.0.0.1/24', defaultRoute='via ' + GW_IP)
        h3 = self.addHost('h3', ip=DNS_IP + '/24', defaultRoute='via ' + GW_IP)

        self.addLink(h1, s1)
        self.addLink(h3, s1)

def start_dns(h3):
    "Uruchamia dnsmasq w przestrzeni nazw h3."
    servers = ' '.join('--server=%s' % s for s in UPSTREAM_DNS)
    h3.cmd('dnsmasq'
           ' --conf-file=/dev/null'        # ignoruj systemowy /etc/dnsmasq.conf
           ' --no-resolv'                  # NIE czytaj /etc/resolv.conf 
           ' --no-hosts'                   # nie odpowiadaj z /etc/hosts
           ' ' + servers +                 # upstream DNS w Internecie
           ' --listen-address=' + DNS_IP +
           ' --bind-interfaces'
           ' --log-queries'
           ' --log-facility=/tmp/dnsmasq-h3.log'
           ' --pid-file=/tmp/dnsmasq-h3.pid')


def stop_dns(h3):
    h3.cmd('kill $(cat /tmp/dnsmasq-h3.pid) 2>/dev/null')


def run(ctrl_ip, ctrl_port):
    net = Mininet(topo=DnsProtectorTopo(),
                  switch=OVSSwitch,
                  controller=None,
                  ipBase='10.0.0.0/24',
                  autoSetMacs=True)       # czytelne MAC-i:

    net.addController('c0', controller=RemoteController,
                      ip=ctrl_ip, port=ctrl_port)

    # Brama NAT, podlaczona do s1
    net.addNAT(ip=GW_IP + '/24').configDefault()

    # Hosty Mininetu wspoldziela system plikow z VM, wiec maja wspolny resolv.conf.
    # Na czas demo kierujemy go na h3, po zakonczeniu przywracamy.
    with open(RESOLV) as f:
        resolv_backup = f.read()

    net.start()
    h3 = net.get('h3')
    start_dns(h3)

    try:
	os.system('resolvconf --disable-updates')
        with open(RESOLV, 'w') as f:
            f.write('nameserver %s\n' % DNS_IP)

        info('* Kontroler: %s:%d\n' % (ctrl_ip, ctrl_port))
        info('* DNS: %s (log: /tmp/dnsmasq-h3.log)\n' % DNS_IP)
        info('* Demo:  h1 dig example.com   |   h1 wget -O - http://example.com\n')
        CLI(net)
    finally:
        with open(RESOLV, 'w') as f:
            f.write(resolv_backup)
	os.system('resolvconf --enable-updates')
        stop_dns(h3)
        net.stop()


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('Uzycie: sudo python %s <IP_KONTROLERA> [PORT]' % sys.argv[0])
        sys.exit(1)
    setLogLevel('info')
    run(sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 6653)
