#!/bin/sh

cd $(dirname $0)

export PREFIX=${PREFIX:-CRON}

echo Starting containers...
id1=$(docker run \
	-d -t \
	-v $(pwd):/mnt \
	-e "${PREFIX}_0=*/1 * * * * /mnt/helper.py --test basic" \
	-e "${PREFIX}_1=&runas(irc) */1 * * * * /mnt/helper.py --test user" \
	-e "${PREFIX}_2=EVAR=some value" \
	-e "${PREFIX}_3=*/1 * * * * /mnt/helper.py --test envvars" \
	-e "${PREFIX}_4=*/1 * * * * /mnt/helper.py --test stdin %line 1%line 2%line 3" \
	python:3 /mnt/helper.py --root basic,envvars,stdin,user)

id2=$(docker run \
	-d -t \
	-v $(pwd):/mnt \
	-e "${PREFIX}_RESTART_0=*/1 * * * *" \
	python:3 /mnt/helper.py --root restart)

id3=$(docker create \
	-t \
	-v $(pwd):/mnt \
	-e "${PREFIX}_0=*/1 * * * * /mnt/helper.py --test basic" \
	-e "${PREFIX}_START_0=*/1 * * * *" \
	python:3 /mnt/helper.py --root start,basic)

onexit() {
	echo ""
	echo Exiting, cleaning up
	docker kill $id1 $id2 $id3
	while docker inspect $id1 >/dev/null 2>&1 && ! docker rm $id1 2>/dev/null; do
		echo docker rm failed, retrying
		docker kill $id1
	done
	while docker inspect $id2 >/dev/null 2>&1 && ! docker rm $id2 2>/dev/null; do
		echo docker rm failed, retrying
		docker kill $id2
	done
	while docker inspect $id3 >/dev/null 2>&1 && ! docker rm $id3 2>/dev/null; do
		echo docker rm failed, retrying
		docker kill $id3
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
ip3=$(ipaddr $id3)

echo -n "Waiting for results.."

deadline=$(date -d '5 minutes' +%s)

while [ "$(date +%s)" -lt $deadline ]; do
	if [ -z "$ip3" ]; then
		ip3=$(ipaddr $id3)
	fi

	# https://superuser.com/questions/590099/can-i-make-curl-fail-with-an-exitcode-different-than-0-if-the-http-status-code-i
	stat1=$(curl --silent --output /dev/null --write-out "%{http_code}" http://$ip1)
	stat2=$(curl --silent --output /dev/null --write-out "%{http_code}" http://$ip2)
	stat3=$(curl --silent --output /dev/null --write-out "%{http_code}" http://$ip3)

	if [ "$stat1" -eq "200" ]; then
		if [ "$stat2" -eq "200" ]; then
			if [ "$stat3" -eq "200" ]; then
				printf "\n\033[32m>>> PASS <<<\033[0m\n"
				exit 0
			fi
		fi
	fi

	if [ "$stat1" -eq "500" ]; then
		printf "\n\033[31m>>> FAIL <<<\033[0m\n"
		echo Container 1 failed
		sleep 1
		docker logs $id1
		exit 1
	fi

	if [ "$stat2" -eq "500" ]; then
		printf "\n\033[31m>>> FAIL <<<\033[0m\n"
		echo Container 2 failed
		sleep 1
		docker logs $id2
		exit 1
	fi

	if [ "$stat3" -eq "500" ]; then
		printf "\n\033[31m>>> FAIL <<<\033[0m\n"
		echo Container 3 failed
		sleep 1
		docker logs $id3
		exit 1
	fi

	echo -n "."
	sleep 2
done

printf "\n\033[31m>>> FAIL <<<\033[0m\n"
echo Timeout expired
exit 1
