#!/usr/bin/env -S uv run --script
# /// script
# requires-python = '>=3.11'
# dependencies = [
#   'click==8.1.8',
#   'substrate-interface==1.7.11',
#   'flask==3.1.0',
#   'waitress==3.0.2',
# ]
# ///

import click
from datetime import datetime, timezone, timedelta, UTC
from flask import Flask
from substrateinterface import SubstrateInterface, SubstrateNodeExtension
import os

# With async backing
RELAY_BLOCK_SECONDS = 6

# Length of timeslice in Relay Chain blocks
# (normal runtime, without the `fast-runtime` feature).
# This value declared here:
# https://github.com/paritytech/polkadot-sdk/blob/2970ab151402a94c146800c769953cf6fdb6ef1d/polkadot/runtime/rococo/constants/src/lib.rs#L133
TIMESLICE_PERIOD = 80

@click.command()
@click.option('--host', type=str, help='Listen address, e.g. 127.0.0.1', required=True)
@click.option('--port', type=str, help='Listen port, e.g. 43987', required=True)
@click.option('--relay-endpoint', type=str, help='Kusama relay node url', default='wss://kusama-rpc.dwellir.com/')
@click.option('--coretime-endpoint', type=str, help='Coretime parachain nodee url', default='wss://kusama-coretime-rpc.polkadot.io/')
@click.option('--task', type=int, help='Parachain Id, e.g. 2095', required=True)
def main(host: str, port: int, relay_endpoint: str, coretime_endpoint: str, task: int):
    debug = os.environ.get('DEBUG') or False

    app = Flask(__name__)
    
    @app.route("/")
    def root():
        return coretime_prometheus(relay_endpoint, coretime_endpoint, task)

    if debug:
        print(f'Listening {host}:{port} with debug server...')
        app.run(host=host, port=port, debug=True, load_dotenv=False)
    else:
        from waitress import serve
        print(f'Listening {host}:{port}...')
        serve(app, host=host, port=port)

def coretime_prometheus(
    relay_endpoint: str,
    coretime_endpoint: str,
    task: int,
):
    with (
        SubstrateInterface(url=relay_endpoint) as relay_sub,
        SubstrateInterface(url=coretime_endpoint) as coretime_sub,
    ):
        block = get_block_info(coretime_sub)

        workload = coretime_sub.query_map('Broker', 'Workload', block_hash=block['hash'])
        core = next(
            core.value
            for core, core_workload in workload
            if core_workload[0]['assignment'][1] == task
        )

        if not core:
            raise f'Task {task} not found!'

        potential_renewals = coretime_sub.query_map('Broker', 'PotentialRenewals', block_hash=block['hash'])
        renew_info = next(
            {'when': key['when'].value, 'price': value['price'].value}
            for key, value in potential_renewals
            if value['completion'][1][0]['assignment'][1].value == task
        )
        
        if not renew_info:
            raise f'Renew info for task {task} not found!'

        renew_dates = calculate_renew_dates(relay_sub, coretime_sub, block, renew_info['when'])
        renew_at = renew_dates['at'].timestamp()
        renew_until = renew_dates['until'].timestamp()
        price = renew_info['price']

        return '\n'.join([
            f'renew_at{{task="{task}"}} {renew_at:.0f}',
            f'renew_until{{task="{task}"}} {renew_until:.0f}',
            f'price{{task="{task}"}} {price}',
            f'core{{task="{task}"}} {core}',
        ])

def get_block_info(sub: SubstrateInterface, block_number: int = None):
    block = sub.get_block(block_number=block_number)
    block_number = block['header']['number']
    block_hash = block['header']['hash']
    block_datetime = None
    
    for e in block['extrinsics']:
        call = e['call']

        if call.call_module.name != 'Timestamp' or call.call_function.name != 'set':
            continue
        
        block_timestamp = call.call_args[0]['value'].value
        block_datetime = datetime.fromtimestamp(block_timestamp / 1000, UTC)

    return {
        'hash': block_hash,
        'number': block_number,
        'datetime': block_datetime
    }

def calculate_renew_dates(
    relay_sub: SubstrateInterface,
    coretime_sub: SubstrateInterface,
    block: any,
    when_renew: int,
):
    config = coretime_sub.query('Broker', 'Configuration', block_hash=block['hash']).value
    
    # 1. Subtract region length to get when we can renew.
    #
    # 'when' is not the timeslice when it can be renewed,
    # but the timeslice for which region will be renewed.
    renew_timeslice = when_renew - config['region_length']

    # 2. Convert timeslice to relay blocks.
    at_relay_block = renew_timeslice * TIMESLICE_PERIOD
    
    # 3. Got the last relay block number and calculate how many block is left
    last_relay_block_number = coretime_sub.query('ParachainSystem', 'LastRelayChainBlockNumber', block_hash=block['hash']).value
    relay_blocks_remaining = at_relay_block - last_relay_block_number
    seconds_remaining = relay_blocks_remaining * RELAY_BLOCK_SECONDS
    
    # 4. Calculate date when we can renew parachain
    relay_block = get_block_info(relay_sub, last_relay_block_number)
    at = relay_block['datetime'] + timedelta(seconds=seconds_remaining)
    
    # 5. Calculate renew end date
    interlude_length = config['interlude_length'] * RELAY_BLOCK_SECONDS
    until = at + timedelta(seconds=interlude_length)

    return {'at': at, 'until': until}

if __name__ == '__main__':
    main()
