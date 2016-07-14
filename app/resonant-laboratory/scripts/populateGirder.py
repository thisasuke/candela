#!/usr/bin/env python
import argparse
import getpass
import girder_client
import os
import json
import sys
import subprocess


def getArguments():
    parser = argparse.ArgumentParser(description='''Populate a girder installation
        with the public library (datasets and projects) for Resonant Laboratory.
        This script is idempotent, so running it multiple times won't
        result in duplicate files (though it may revert any changes
        that have been made to the elements that it originally added)''')
    parser.add_argument('-u', dest='username', default='admin',
                        help='The administrator username (default: "admin")')
    parser.add_argument('-a', dest='apiUrl',
                        default='http://localhost:8080/api/v1',
                        help='The url of the Girder instance\'s API endpoint.')
    parser.add_argument('-c', dest='clean', action='store_true',
                        help='Remove the ResonantLaboratory collection before re-populating')
    parser.add_argument('-d', dest='databaseThreshold', default='131072',
                        help='If a file exceeds this threshold (in bytes), upload it as a ' +
                        'mongo database collection instead of a flat file.')
    parser.add_argument('-m', dest='mongoHost',
                        default='localhost',
                        help='The server hosting the mongo instance in which to store larger files.')
    parser.add_argument('-p', dest='mongoPort',
                        default='27017',
                        help='The port of the mongo instance in which to store larger files.')
    parser.add_argument('-n', dest='dbName',
                        default='resonantLaboratoryLibrary',
                        help='The name of the mongo db to use for larger files.')

    return parser.parse_args()


def getGirderCollection(args):
    print 'Enter the password for Girder user "' + args.username + '":'
    password = getpass.getpass()

    gc = girder_client.GirderClient(apiUrl=args.apiUrl)
    gc.authenticate(args.username, password)

    message = ''

    # Get or create the ResonantLaboratory collection
    collection = gc.sendRestRequest('GET', 'collection',
                                    {'text': 'ResonantLaboratory'})

    # If specified, trash the existing ResonantLaboratory collection
    if (args.clean):
        if (len(collection) == 0):
            print 'No "ResonantLaboratory" collection to clean.'
            print
        else:
            gc.sendRestRequest('DELETE', 'collection/' + collection[0]['_id'])
            print 'Deleted "ResonantLaboratory" collection.'
            print
            collection = []

    # Create a new collection if needed
    if len(collection) == 0:
        collection = gc.sendRestRequest('POST', 'collection',
                                        {'name': 'ResonantLaboratory',
                                         'description': 'The public library for' +
                                                        ' the Resonant ' +
                                                        'Laboratory Application',
                                         'public': True})
        message += 'Created collection '
    else:
        collection = collection[0]
        message += 'Using existing collection '
    collectionID = collection['_id']

    message += collectionID
    print message
    print ''.join(['=' for x in message])   # underline

    return (gc, collectionID)


def createMongoCollection(args, filePath, fileName):
    # TODO: do this with pymongo, not mongo-import
    parts = os.path.splitext(fileName)
    command = ['mongoimport',
               '--host', args.mongoHost,
               '--port', args.mongoPort,
               '--db', args.dbName,
               '--collection', parts[0],
               '--drop',
               '--file', os.path.join(filePath, fileName)]
    if parts[1].lower() == '.csv':
        command.extend(['--type', 'csv',
                        '--headerline'])
    else:
        command.append('--jsonArray')
    subprocess.check_output(command, stderr=subprocess.STDOUT)


if __name__ == '__main__':
    args = getArguments()
    gc, collectionID = getGirderCollection(args)

    # Create the Data and Projects folders
    dataItemIdLookup = {}
    for folder in ['examples/Data', 'examples/Projects']:
        if not os.path.isdir(folder):
            continue

        print
        print '## ' + folder + ':'
        print ''

        folderSpec = gc.load_or_create_folder(os.path.split(folder)[1],
                                              collectionID,
                                              'collection')

        # The second-level directories correspond to items
        items = os.listdir('./' + folder)
        if len(items) == 0:
            continue

        longestItemName = max([len(item) for item in items])

        print 'Item' + ''.join([' ' for x in xrange(longestItemName - 4)]),
        print '\tIgnored files\tFlat files added\tMongo Collections added\tMetadata attached\tSuppressed Item'

        for item in items:
            if not os.path.isdir('./' + folder + '/' + item):
                continue
            print item,
            suppressItem = False

            spacesNeeded = longestItemName - len(item)
            message = ''.join([' ' for x in xrange(spacesNeeded)])

            # Create (or get) the item
            itemSpec = gc.load_or_create_item(item, folderSpec['_id'])

            # If this is a dataset, store its ID for Projects
            # to look up later
            if folder == 'examples/Data':
                dataItemIdLookup[item] = itemSpec['_id']

            # Now upload any files that don't already
            # exist in the item
            files = os.listdir('./' + folder + '/' + item)

            existingFiles = gc.sendRestRequest('GET', 'item/' + itemSpec['_id'] + '/files', {})
            existingFiles = set([x['name'] for x in existingFiles])

            ignoredFiles = 0
            addedFiles = 0
            addedCollections = 0
            skippedFiles = 0
            addedMetadata = False

            # Load each of the files into the item
            for fileName in files:
                if fileName == 'metadata.json':
                    # metadata.json is special; attach it as the item's
                    # metadata instead of uploading it as a file
                    temp = open('./' + folder + '/' + item + '/metadata.json', 'rb')
                    contents = temp.read()
                    metadata = {
                        'rlab': json.loads(contents)
                    }
                    temp.close()

                    # If this is a project, we need to replace the dataset
                    # folder name with a Girder ID
                    if folder == 'examples/Projects':
                        for i, d in enumerate(metadata['rlab']['datasets']):
                            if d['itemId'] not in dataItemIdLookup:
                                # Hmm... the dataset that this project is
                                # referring to doesn't exist
                                suppressItem = True
                            else:
                                metadata['rlab']['datasets'][i]['dataset'] = dataItemIdLookup[d['itemId']]
                    if not suppressItem:
                        gc.addMetadataToItem(itemSpec['_id'], metadata)
                        addedMetadata = True
                elif fileName in existingFiles:
                    ignoredFiles += 1
                else:
                    fileSize = os.stat('./' + folder + '/' + item + '/' + fileName).st_size
                    if (fileSize > int(args.databaseThreshold)) or os.path.splitext(fileName)[1] == '.json':
                        # For now, we skip large / json files and suppress the dataset item
                        if item in dataItemIdLookup:
                            del dataItemIdLookup[item]
                        suppressItem = True
                        '''createMongoCollection(args, './' + folder + '/' + item + '/', fileName)
                        gc.sendRestRequest('POST', 'item/' + itemSpec['_id'] + '/database', {}, json.dumps({
                            'url': args.mongoHost + ':' + args.mongoPort,
                            'database': args.dbName,
                            'collection': os.path.splitext(fileName)[0],
                            'type': 'mongo'
                        }))
                        addedCollections += 1'''
                    else:
                        gc.uploadFileToItem(itemSpec['_id'], './' + folder + '/' + item + '/' + fileName)
                        addedFiles += 1

            # Hit the endpoint that identifies the item as a dataset or a project,
            # and populates the metadata appropriately
            if suppressItem:
                gc.delete('item/' + itemSpec['_id'])
            else:
                if folder == 'examples/Data':
                    gc.sendRestRequest('POST', 'item/' + itemSpec['_id'] + '/dataset')
                elif folder == 'examples/Projects':
                    gc.sendRestRequest('POST', 'item/' + itemSpec['_id'] + '/project')

            message += '\t%i            \t%i               \t%i                \t%s                \t%s' % (
                ignoredFiles, addedFiles, addedCollections,
                'Y' if addedMetadata else 'N',
                'Y' if suppressItem else 'N')
            print message

    print 'finished'
    print
