import argparse
import ConfigParser
import os
import subprocess
import sys
import urllib2
import zlib

try:
    import simplejson as json
except ImportError:
    import json

from gondor import __version__
from gondor import http, utils


def cmd_deploy(args, config):
    label = args.label[0]
    commit = args.commit[0]
    
    gondor_dirname = ".gondor"
    repo_root = utils.find_nearest(os.getcwd(), gondor_dirname)
    tarball = None
    
    try:
        sys.stdout.write("Reading configuration... ")
        local_config = ConfigParser.RawConfigParser()
        local_config.read(os.path.join(repo_root, gondor_dirname, "config"))
        client_key = local_config.get("gondor", "client_key")
        sys.stdout.write("[ok]\n")
        
        sys.stdout.write("Building tarball from %s... " % commit)
        tarball = os.path.abspath(os.path.join(repo_root, "%s.tar.gz" % label))
        cmd = "(cd %s && git archive --format=tar %s | gzip > %s)" % (repo_root, commit, tarball)
        subprocess.call([cmd], shell=True)
        sys.stdout.write("[ok]\n")
        
        text = "Pushing tarball to Gondor... "
        sys.stdout.write(text)
        url = "http://gondor.eldarion.com/deploy/"
        mgr = urllib2.HTTPPasswordMgrWithDefaultRealm()
        mgr.add_password(None, url, config["username"], config["password"])
        opener = urllib2.build_opener(
            urllib2.HTTPBasicAuthHandler(mgr),
            http.MultipartPostHandler,
            http.UploadProgressHandler
        )
        params = {
            "version": __version__,
            "client_key": client_key,
            "label": label,
            "tarball": open(tarball, "rb"),
        }
        response = opener.open(url, params)
        data = json.loads(response.read())
        if data["status"] == "error":
            message = data["message"]
        elif data["status"] == "success":
            message = "ok"
        else:
            message = "unknown"
        sys.stdout.write("\r%s[%s]   \n" % (text, message))
    finally:
        if tarball:
            os.unlink(tarball)


def cmd_sqldump(args, config):
    label = args.label[0]
    
    gondor_dirname = ".gondor"
    repo_root = utils.find_nearest(os.getcwd(), gondor_dirname)
    
    config = ConfigParser.RawConfigParser()
    config.read(os.path.join(repo_root, gondor_dirname, "config"))
    client_key = config.get("gondor", "client_key")
    
    # request SQL dump and stream the response through uncompression
    
    d = zlib.decompressobj(16+zlib.MAX_WBITS)
    sql_url = "http://gondor.eldarion.com/sqldump/"
    mgr = urllib2.HTTPPasswordMgrWithDefaultRealm()
    mgr.add_password(None, sql_url, config["username"], config["password"])
    opener = urllib2.build_opener(urllib2.HTTPBasicAuthHandler(mgr))
    params = {
        "version": __version__,
        "client_key": client_key,
        "label": label,
    }
    response = opener.open(sql_url, params)
    cs = 16 * 1024
    while True:
        chunk = response.read(cs)
        if not chunk:
            break
        sys.stdout.write(d.decompress(chunk))
        sys.stdout.flush()


def main():
    parser = argparse.ArgumentParser(prog="gondor")
    parser.add_argument("--version", action="version", version="%%(prog)s %s" % __version__)
    
    command_parsers = parser.add_subparsers(dest="command")
    
    # cmd: deploy
    parser_deploy = command_parsers.add_parser("deploy")
    parser_deploy.add_argument("label", nargs=1)
    parser_deploy.add_argument("commit", nargs=1)
    
    # cmd: sqldump
    parser_sqldump = command_parsers.add_parser("sqldump")
    parser_sqldump.add_argument("label", nargs=1)
    
    args = parser.parse_args()
    
    # config
    
    config = ConfigParser.RawConfigParser()
    config.read(os.path.expanduser("~/.gondor"))
    config = {
        "username": config.get("auth", "username"),
        "password": config.get("auth", "password"),
    }
    
    {
        "deploy": cmd_deploy,
        "sqldump": cmd_sqldump
    }[args.command](args, config)
