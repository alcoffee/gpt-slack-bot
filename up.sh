docker rm -f slack
docker run -v "$PWD/src:/gpt-slack-bot/" -d \
        --name slack -it gpt-slack-bots
