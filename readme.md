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
   Where `--task` is your parachain id
4. Go to 127.0.0.1:43987 and got information of next renew for your Prometheus

## License

The project is licensed under the [MIT License](license)