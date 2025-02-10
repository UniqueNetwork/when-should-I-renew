# When should I renew?

Microservice for providing information about the next parachain renew in Prometheus format

## Usage

1. [Install UV](https://docs.astral.sh/uv/getting-started/installation/)
2. Make app.py executable: `chmod +x ./app.py`
3. Run script:
   ```shell
   ./app.py \
     --host 127.0.0.1 \
     --port 43987 \
     --endpoint wss://kusama-coretime-rpc.polkadot.io/ \
     --task 2095
   ```
   Where `--task` is your parachain id.
   If you want to debug service, set env var `DEBUG` to `True`
4. Go to 127.0.0.1:43987 and got information of next renew for your Prometheus

## Metrics

- `renew_at`: timestamp (in seconds) when the next interlude period will begin, during which renew can be made
- `renew_until`: timestamp (in seconds) when the interlude period will end, and renew can no longer be made
- `price`: cost of the renew; to get the price in KSM, you need to divide this by 10^18
- `core`: number of the current core on which the parachain is running, and it will change after the renew

Each metric has a label `task`, which is the parachain ID to which the values pertain; this is done for future purposes in case multiple parachains need to be monitored

Example:

```prometheus
renew_at{task="2095"} 1740798352
renew_until{task="2095"} 1741100752
price{task="2095"} 791756500
core{task="2095"} 27
```

## License

The project is licensed under the [MIT License](license)