import sqlite3,os

class sqlMerge(object):
    """Basic python script to merge data of 2 !!!IDENTICAL!!!! SQL tables"""

    def __init__(self):

        self.db_a = None
        self.db_b = None

    def merge(self, file_a, file_b):

        self.db_a = sqlite3.connect(file_a)

        cursor_a = self.db_a.cursor()
        cursor_a.execute("SELECT name FROM sqlite_master WHERE type='table';")

        table_list=[]
        for table_item in cursor_a.fetchall():
            table_list.append(table_item[0])

        cursor_a = self.db_a.cursor()

        cmd = "attach ? as toMerge"
        cursor_a.execute(cmd, (file_b, ))

        for table_name in table_list:

            new_table_name = table_name + "_new"

            try:
                cmd = "CREATE TABLE IF NOT EXISTS {0} AS SELECT * FROM {1};".format(new_table_name,table_name)
                cursor_a.execute(cmd)

                cmd = "INSERT INTO {0} SELECT * FROM toMerge.{1};".format(new_table_name,table_name)
                cursor_a.execute(cmd)

                cursor_a.execute("DROP TABLE IF EXISTS " + table_name);
                cursor_a.execute("ALTER TABLE " + new_table_name + " RENAME TO " + table_name);

                self.db_a.commit()

            except sqlite3.OperationalError:
                print("ERROR!: Merge Failed for " + new_table_name)
                cursor_a.execute("DROP TABLE IF EXISTS " + new_table_name);

            finally:
                if table_name == table_list[-1]:
                    cmd = "detach toMerge"
                    cursor_a.execute(cmd, ())
                    self.db_a.close()

        return

    def mergelist(self, file_a, merge_list):

        from datetime import datetime
        from shutil import copy2, move
        from os import remove, path, makedirs

        try:
            assert type(merge_list) == list
        except (AssertionError):
            print ('Failed assertion to ensure merge files are a list')
            raise
        except:
            print ('Unexpected Error')
            raise

            try:
                assert os.path.exists(file_a)
            except (AssertionError):
                print ('Failed assertion to ensure master file exists')
                raise
            except:
                print ('Unexpected Error')
                raise

        copy2(file_a,file_a+"_bak")

        for file in merge_list:

            try:
                assert os.path.exists(file)
            except (AssertionError):
                print ('Failed assertion to ensure merge file exists')
                raise
            except:
                print ('Unexpected Error')
                raise

            self.merge(file_a, file)

        timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")

        hostname = os.popen('hostname').read().strip()

        #uploadfile = '.'.join(file_a.split('.')[:-1])+timestamp+'.'+file_a.split('.')[-1] # filename with timestamp added, preserving all . characters
        uploadfile = "upload_"+hostname+"_"+timestamp+".db"

        savepath = '/home/serverpi/uploadedData'

        if not path.exists(savepath):
            print('Directory to store uploaded data'
                + ' does not exist\nAttempting to create:')
            makedirs(savepath)

        success=self.upload_s3(file_a,'bib-pilot-bucket',uploadfile)

        if success:

            copy2(file_a, os.path.join(savepath,uploadfile))

            for file in merge_list:
                remove(file)
            remove(file_a)
            remove(file_a+"_bak")

            return True

        else:

            move(file_a+"_bak", file_a)

            return False

    def upload_s3(self, file_name, bucket, object_name=None):

        import boto3
        import logging
        from botocore.exceptions import ClientError

        """Upload a file to an S3 bucket

            :param file_name: File to upload
            :param bucket: Bucket to upload to
            :param object_name: S3 object name. If not specified then file_name is used
            :return: True if file was uploaded, else False
        """

        # If S3 object_name was not specified, use file_name
        if object_name is None:
            object_name = file_name

        # Upload the file
        s3_client = boto3.client('s3')
        try:
            response = s3_client.upload_file(file_name, bucket, object_name)
        except ClientError as e:
            logging.error(e)
            return False
        return True

    # Sharepoint upload - requires uname and password in plain text

    def upload_sp (self, file_name, username, password):

        from office365.runtime.auth.authentication_context import AuthenticationContext
        from office365.runtime.auth.user_credential import UserCredential
        from office365.sharepoint.client_context import ClientContext
        from datetime import datetime

        baseurl = 'https://leeds365.sharepoint.com'
        basesite = '/sites/TEAM-BiB-Breathes'
        siteurl = baseurl + basesite
        localpath = file_name
        timestamp=datetime.utcnow().strftime("%Y%m%d%H%M%S")
        remotepath = 'Shared%20Documents/db_files/server_{}.db'.format(timestamp)
        credentials = UserCredential(username, password)
        #ctx_auth = AuthenticationContext(siteurl)
        #ctx_auth.acquire_token_for_user(username, password)
        #ctx = ClientContext(siteurl, ctx_auth)
        ctx = ClientContext(siteurl).with_credentials(credentials)
        with open(localpath, 'rb') as content_file:
            file_content = content_file.read()

        dir, name = os.path.split(remotepath)
        file = ctx.web.get_folder_by_server_relative_url(dir).upload_file(name, file_content).execute_query()
