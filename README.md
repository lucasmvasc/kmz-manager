# KMZ Manager

KMZ Manager is a Flask application that provides an API for managing KMZ (Keyhole Markup Language Zipped) files. It uses MongoDB as the database to store and retrieve KMZ data.

## Prerequisites

- Python 3.x
- MongoDB
- Ubuntu or any other Linux distribution (the instructions are for Ubuntu)

## Setting up the Environment

1. **Install Python 3.x and pip**

```bash
sudo apt-get update
sudo apt-get install -y python3 python3-pip
```

2. **Clone the repository**

```bash
git clone https://github.com/your-repo/kmz-manager.git
```

3. **Create a virtual environment and activate it**

```bash
cd kmz-manager
python3 -m venv venv
source venv/bin/activate
```

4. **Install the required Python packages**

```bash
pip install -r requirements.txt
```

5. **Set the MongoDB connection URI**

Create a `.env` file in the project root directory and add the following line, replacing the URI with your MongoDB connection string:

```
MONGO_URI=mongodb://your-mongodb-uri
```

## Running the Application

### Development

To run the application in development mode, execute:

```bash
python app.py
```

The application will be accessible at `http://localhost:5000`.

### Production

For production deployment, we will use Gunicorn with Supervisor and Nginx.

1. **Install Gunicorn, Supervisor, and Nginx**

```bash
sudo apt-get install -y gunicorn supervisor nginx
```

2. **Configure Supervisor**

Create a new configuration file for the KMZ Manager application in `/etc/supervisor/conf.d/kmz-manager.conf`:

```ini
[program:kmz-manager]
command=/home/ubuntu/kmz-manager/venv/bin/gunicorn -w 3 -b unix:/home/ubuntu/kmz-manager/kmz_manager.sock app:app
directory=/home/ubuntu/kmz-manager
user=ubuntu
autostart=true
autorestart=true
stopasgroup=true
killasgroup=true
```

After creating the file, run the following commands to update Supervisor and start the application:

```bash
sudo supervisorctl reread
sudo supervisorctl update
sudo supervisorctl start kmz-manager
```

3. **Configure Nginx**

Create a new configuration file for the KMZ Manager application in `/etc/nginx/sites-available/kmz-manager`:

```nginx
server {
    listen 80;
    server_name your-server-ip-or-domain;

    location / {
        proxy_pass http://unix:/home/ubuntu/kmz-manager/kmz_manager.sock;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
    }
}
```

After creating the file, enable the configuration and restart Nginx:

```bash
sudo ln -s /etc/nginx/sites-available/kmz-manager /etc/nginx/sites-enabled/
sudo systemctl restart nginx
```

The application should now be accessible at `http://your-server-ip-or-domain`. <br>
FYI: if you're using a Virtual Machine, make sure to set your public Ipv4.

## API Endpoints

The following endpoints are available in the KMZ Manager API:

- `GET /kmzs`: Retrieve a list of all KMZ files.
- `GET /kmzs/<kmz_id>`: Retrieve a specific KMZ file by its ID.
- `POST /kmzs`: Add a new KMZ file.
- `PUT /kmzs/<kmz_id>`: Update an existing KMZ file by its ID.
- `DELETE /kmzs/<kmz_id>`: Delete a KMZ file by its ID.

## MongoDB Usage

The application uses the `flask_pymongo` library to interact with MongoDB. The database connection is established in `app.py` using the `MONGO_URI` environment variable.

The `db` variable holds the reference to the `alagaprev` database, and the `collection` variable holds the reference to the `kmzs` collection, which is used to perform CRUD operations on KMZ data.

Each API endpoint uses the appropriate MongoDB methods from the `flask_pymongo` library to interact with the `kmzs` collection.

For example, the `get_kmzs` function uses the `find` method to retrieve all KMZ documents from the collection:

```python
kmzs = collection.find({}, {"_id": 0})
return jsonify(list(kmzs))
```

Similarly, the `add_kmz` function uses the `insert_one` method to add a new KMZ document to the collection:

```python
kmz_data = request.get_json()
result = collection.insert_one(kmz_data)
return jsonify({"_id": str(result.inserted_id)})
```

The other endpoints (`get_kmz`, `update_kmz`, and `delete_kmz`) use the corresponding MongoDB methods (`find_one`, `update_one`, and `delete_one`) to perform their respective operations.
