# Schedule-RTU


Service for getting jsons with a schedule for a given group of RTU MIREA

The app now reads the public RTU MIREA schedule site directly, stores parsed group schedules in MongoDB, and exposes them through the API.

# Build service from Docker image
Requirements:
* Docker

## Run locally with Docker Compose

Start the stack:
* ```docker compose up -d --build```

Open the API docs:
* ```http://localhost:5000/docs```

Refresh the schedule cache:
* ```POST http://localhost:5000/api/refresh?secret_key=secret```

Get the list of available groups:
* ```GET http://localhost:5000/api/schedule/groups```

Get the full schedule for a group:
* ```GET http://localhost:5000/api/schedule/{group}/full_schedule```

The root path redirects to ```/docs```. If you set a different refresh secret in ```.env``, use that value in the refresh request.

## Deploy

Run next command to generate swarm stack file
```bash
# bash
docker-compose -f docker-compose.yml -f docker-compose.production.yml config | sed "s/[0-9]\+\.[0-9]\+$/'\0'/g" >| stack.yml
```
