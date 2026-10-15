# Setup

No API key, no internet needed after install.

```bash
cd ~/Downloads/signal-outbound
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
make test
make demo
make naive
```
