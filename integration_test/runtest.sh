#!/bin/sh

cd $(dirname $0)

export PREFIX=${PREFIX:-CRON}

echo Starting containers...
id1=$(docker run \
	-d -t \
	-v $(pwd):/mnt \
	-e "${PREFIX}_0=*/1 * * * * /mnt/run.py --test 0" \
	-e "${PREFIX}_1=&runas(irc) */1 * * * * /mnt/run.py --test 1" \
	-e "${PREFIX}_2=EVAR=some value" \
	-e "${PREFIX}_3=*/1 * * * * /mnt/run.py --test 2" \
	-e "${PREFIX}_4=*/1 * * * * /mnt/run.py --test 3 %line 1%line 2%line 3" \
	python:3 /mnt/run.py --root 4)

id2=$(docker run \
	-d -t \
	-v $(pwd):/mnt \
	-e "${PREFIX}_RESTART_0=*/1 * * * *" \
	python:3 /mnt/run.py --root restart)

onexit() {
	echo ""
	echo Exiting, cleaning up
	docker kill $id1 $id2
	while ! docker rm $id1 2>/dev/null; do
		echo docker rm failed, retrying
		docker kill $id1
	done
	while ! docker rm $id2 2>/dev/null; do
		echo docker rm failed, retrying
		docker kill $id2
	done
}
onsig() {
	trap - SIGHUP SIGINT SIGTERM
	onexit
	exit 1
}
trap onsig SIGHUP SIGINT SIGTERM
trap onexit EXIT

ipaddr() {
	docker inspect $1 | python3 -c "import json, sys; j = json.load(sys.stdin); net = j[0]['NetworkSettings']['Networks']; n = list(net.keys())[0]; print(net[n]['IPAddress'])"
}

ip1=$(ipaddr $id1)
ip2=$(ipaddr $id2)

echo -n "Waiting for results.."

while :
do
	# https://superuser.com/questions/590099/can-i-make-curl-fail-with-an-exitcode-different-than-0-if-the-http-status-code-i
	stat1=$(curl --silent --output /dev/null --write-out "%{http_code}" http://$ip1)
	stat2=$(curl --silent --output /dev/null --write-out "%{http_code}" http://$ip2)

	if [ "$stat1" -eq "200" ]; then
		if [ "$stat2" -eq "200" ]; then
			echo ""
			echo "Success!"
			exit 0
		fi
	fi

	if [ "$stat1" -eq "500" ]; then
		echo ""
		echo Container 1 failed
		sleep 1
		docker logs $id1
		exit 1
	fi

	if [ "$stat2" -eq "500" ]; then
		echo ""
		echo Container 2 failed
		sleep 1
		docker logs $id2
		exit 1
	fi

	echo -n "."
	sleep 2
done
