# regular imports
import binascii
import argparse
import sys
import os.path

# from requirements.txt
import requests

# type hint support
from typing import List, Dict, Any, Tuple

# secret file, containing API key on one line
SECRETS = '.secret'

nextdns_api = "https://api.nextdns.io"

# check that file is valid with argparse (thank you stackoverflow)
def is_valid_file(parser, arg):
    if not os.path.exists(arg):
        parser.error(f"The file {arg} does not exist.")
    else:
        return open(arg, 'r')

def domain_in_denylist(domain: str, denylist: List[Any]) -> Tuple[Any, Any]:
    '''
        Check if domain is in denylist

        Returns tuple of (present: boolean, index: int)
    '''
    index = 0
    for item in denylist:
        if domain.lower() == item['id'].lower():
            return (True, index)
        index += 1

    return (False, -1)

def get_key() -> Dict[str, str]:
    '''
        Parsing key from SECRETS and testing validity
    '''

    # open file
    with open(SECRETS, 'r') as sf:
        key = sf.readline().strip()

    # make headers obj
    headers = {"X-Api-Key": key, "Accept": "Application/json"}

    # make request to API
    r = requests.get(f"{nextdns_api}/profiles", headers=headers)

    # Non-200 response
    if not r.ok:
        raise Exception("Bad key or NextDNS infrastructure outage")
        
    return headers


def get_blocked_domains(headers: Dict[str, str], profile_id: str = None) -> Tuple[List[Any], str]:
    '''
        Get list of current blocked domains in profile
    '''

    # if profile_id not specified, pick the first profile
    if profile_id is None:
        r = requests.get(f"{nextdns_api}/profiles", headers=headers)
        if r.ok:
            profile_id = r.json().get('data', [])[0].get('id')
            profile_name = r.json().get('data', [])[0].get('name')
    
            # say which profile you picked
            print(f"Found '{profile_name}' ({profile_id})")

    # get the denylist
    r = requests.get(f"{nextdns_api}/profiles/{profile_id}/denylist", headers=headers)
    if r.ok:
        # return list and profile_id
        return (r.json().get('data', []), profile_id)

def block_domains(headers: Dict[str, str], profile_id: str, domains: List[str], denylist: List[Any]) -> bool:
    '''
        Take profile denylist and combine with file argument w/ domains to make new denylist in profile

        Ensure domains from file are marked 'active': True in profile
    '''

    for domain in domains:
        (presence, index) = domain_in_denylist(domain, denylist)
        if presence:
            denylist[index]['active'] = True
        else:
            denylist.append({'id': domain, 'active': True})

    r = requests.patch(f"{nextdns_api}/profiles/{profile_id}", json={"denylist": denylist}, headers=headers)
    return r.ok

def unblock_domains(headers: Dict[str, str], profile_id: str, domains: List[str], denylist: List[Any]) -> bool:
    '''
        Take profile denylist and combine with file argument w/ domains to make new denylist in profile
        
        Ensure domains from file are marked 'active': False in profile
    '''

    for domain in domains:
        (presence, index) = domain_in_denylist(domain, denylist)
        if presence:
            denylist[index]['active'] = False
        else:
            print(f"[*] Weird. '{domain}' not in denylist.")

    r = requests.patch(f"{nextdns_api}/profiles/{profile_id}", json={"denylist": denylist}, headers=headers)
    return r.ok

if __name__ == "__main__":
    # setting up argparse
    parser = argparse.ArgumentParser(description='Block and un-block domains via NextDNS.')
    parser.add_argument('-f', dest='file', required=True, help="txt file w/ line-separated list of domains",
            metavar="FILE", type=lambda x: is_valid_file(parser, x))
    parser.add_argument('-p', help="Profile ID for applicable NextDNS profile",
            dest='nextdns_profile', metavar="PROFILE_ID")
    
    # make group for parser
    group = parser.add_mutually_exclusive_group()
    
    # block and un-block should be separated
    group.add_argument('--block', action='store_true')
    group.add_argument('--un-block', action='store_true')

    args = parser.parse_args()

    # parse key and build HTTP headers from SECRETS file
    try:
        headers = get_key()
    except FileNotFoundError as e:
        print(e)
        sys.exit(-1)
    except Exception as e:
        print("Error testing NextDNS API key:", e)
        sys.exit(-1)

    # get blocked domain list
    (denylist_domains, profile_id) = get_blocked_domains(headers, profile_id = args.nextdns_profile)

    # it would be odd to have no domains in this list. perhaps we hit an error somewhere.
    if len(denylist_domains) == 0:
        answer = input("[*] No domains in denylist. Something could be wrong. Continue? [Y/n]: ")
        if answer.lower().strip().startswith("n"):
            print("[*] Quitting...")
            sys.exit(0)

    # get domains from file
    domain_read = args.file.readlines()
    # clean up domains
    domains = [d.lower().strip() for d in domain_read]

    # if asked to block
    if args.block:
        suc = block_domains(headers, profile_id, domains, denylist_domains)

    # if asked to un-block
    if args.un_block:
        suc = unblock_domains(headers, profile_id, domains, denylist_domains)

    print(f"Success: {suc}")