#!/usr/bin/env -S uv run --script
# /// script
# requires-python = '==3.11.11'
# dependencies = [
#   'click==8.1.8',
#   'substrate-interface==1.7.11',
#   'flask==3.1.0',
#   'waitress==3.0.2',
# ]
# ///

import click
from datetime import datetime, timezone, timedelta
from flask import Flask
from substrateinterface import SubstrateInterface, SubstrateNodeExtension
import os

RELAY_BLOCK_SECONDS = 6
TIMESLICE_PERIOD = 80  # In Relay Chain blocks (normal runtime, without the `fast-runtime` feature).

@click.command()
@click.option('--host', type=str, help='Listen address, e.g. 127.0.0.1', required=True)
@click.option('--port', type=str, help='Listen port, e.g. 43987', required=True)
@click.option('--endpoint', type=str, help='Coretime parachain url, e.g. wss://kusama-coretime-rpc.polkadot.io/', required=True)
@click.option('--task', type=int, help='Parachain Id, e.g. 2095', required=True)
def main(host: str, port: int, endpoint: str, task: int):
    debug = os.environ.get('DEBUG') or False

    app = Flask(__name__)
    
    @app.route("/")
    def root():
        return coretime_prometheus(endpoint, task)

    if debug:
        print(f'Listening {host}:{port} with debug server...')
        app.run(host=host, port=port, debug=True, load_dotenv=False)
    else:
        from waitress import serve
        print(f'Listening {host}:{port}...')
        serve(app, host=host, port=port)

def coretime_prometheus(endpoint: str, task: int):
    sub = SubstrateInterface(url=endpoint)

    block_number = sub.query('System', 'Number').value
    previous_block_number = block_number - 1

    block_hash = sub.query('System', 'BlockHash', [previous_block_number]).value

    workload = sub.query_map('Broker', 'Workload', block_hash=block_hash)
    core = next(
        core.value
        for core, core_workload in workload
        if core_workload[0]['assignment'][1] == task
    )

    if not core:
        raise f'Task {task} not found!'

    potential_renewals = sub.query_map('Broker', 'PotentialRenewals', block_hash=block_hash)
    renew_info = next(
        {'when': key['when'].value, 'price': value['price'].value}
        for key, value in potential_renewals
        if value['completion'][1][0]['assignment'][1].value == task
    )
    
    if not renew_info:
        raise f'Renew info for task {task} not found!'

    when = calculate_renew_dates(sub, renew_info['when'], block_hash)
    renew_at = when['at'].timestamp()
    renew_until = when['until'].timestamp()
    price = renew_info['price']

    return '\n'.join([
        f'renew_at{{task="{task}"}} {renew_at:.0f}',
        f'renew_until{{task="{task}"}} {renew_until:.0f}',
        f'price{{task="{task}"}} {price}',
        f'core{{task="{task}"}} {core}',
    ])

def calculate_renew_dates(sub: SubstrateInterface, when: int, block_hash: str):
    config = sub.query('Broker', 'Configuration', block_hash=block_hash).value
    
    renew_timeslice = when - config['region_length']
    at_relay_block = renew_timeslice * TIMESLICE_PERIOD
    last_relay_block = sub.query('ParachainSystem', 'LastRelayChainBlockNumber', block_hash=block_hash).value
    relay_blocks_remaining = at_relay_block - last_relay_block
    seconds_remaining = relay_blocks_remaining * RELAY_BLOCK_SECONDS
    at = datetime.now(tz=timezone.utc) + timedelta(seconds=seconds_remaining)
    
    interlude_length = config['interlude_length'] * RELAY_BLOCK_SECONDS
    until = at + timedelta(seconds=interlude_length)

    return {'at': at, 'until': until}

if __name__ == '__main__':
    main()
