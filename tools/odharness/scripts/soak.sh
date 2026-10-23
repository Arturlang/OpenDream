cd "$(dirname "$0")/.."
for i in $(seq 1 12); do
  t=$(date +%T)
  srv=$(python -I odh.py threads od-server 20 | head -3 | tr '\n' ' ')
  log=$(stat -c %s out/od_server.log)
  echo "$t $srv | server log bytes=$log"
  sleep 100
done
