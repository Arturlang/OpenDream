# helmexp.sh NAME [DEFINE...]: rebuild the OD test copy with defines, restart server AND client, capture the human
cd "$(dirname "$0")/.."
name=$1; shift
G=${TGMC:-/e/GithubRepos/TerraGov-Marine-Corps}
defs=""; for d in "$@"; do defs="$defs -D $d"; done
python -I odh.py stop od > /dev/null
python -I odh.py compile-od $G tgmc_odtest.dme -D AUTO_HUMAN $defs | tail -1
python -I odh.py od-server $G --json tgmc_odtest.json | tail -1
python -I odh.py od-client $G > /dev/null
python -I odh.py place od 900 760 > /dev/null
sleep 14
python -I odh.py shot exp_$name od | tail -1
