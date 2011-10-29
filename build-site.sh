apt-get install libxml2-dev libxslt-dev

. code/env/bin/activate

# Install the requirements
pip install -r https://raw.github.com/ericmoritz/tvservice/master/requirements.txt

# Fetch the tvservice.py module from github
curl https://raw.github.com/ericmoritz/tvservice/master/tvservice.py > code/app/tvservice.py
