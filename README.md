# TravianAuto

**Welcome to TravianAuto!**

TravianAuto is built to automate some of Travian's repetitive tasks for you. Currently supported tasks are:

**Available Features:**

- Release:
    - Sending hero on adventures
    - Raiding
- Testing:
    - Upgrading resource fields

**Setting up Bright Data Proxy Manager:**
- 1. Create Bright Data account and setup a Proxy Zone. Residential Dedicated IPs are preferred to reduce ban rate
- 2. Download auth key from the link below and add to keychain: 
    - https://raw.githubusercontent.com/luminati-io/luminati-proxy/master/bin/ca.crt
- 3. Install the Bright Data Proxy Manager by running the following cmd within a terminal:
    - `curl -L https://brightdata.com/static/lpm/luminati-proxy-latest-setup.sh | bash`
- 4. Run Proxy Manager with the following cmd. Do not close the terminal session you use to start this process:
    - `proxy-manager`
- 5. Navigate to localhost:22999 in a web browser and login to the Proxy Manager
- 6. Create as many proxy ports as the number of accounts you are expecting to automate.

**Steps to run:**

- 1. Create Travian accounts on your server(s) of choice
- 2. Sign up for Travian's Gold Club to gain access to the Farm List page
- 3. Create a minimum of one farm list to automate raids for
- 4. Run all code blocks within notebook
- 5. Copy site URL after logging into server and include within "Site:" input request
- 6. Input usernames and passwords for each site as you are prompted
- 7. ???
- 8. Profit