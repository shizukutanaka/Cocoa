import os
import argparse
# pip install dropbox で利用可
try:
    import dropbox
except ImportError:
    dropbox = None

def upload_dir_to_dropbox(local_dir, dropbox_token, dropbox_dir):
    if dropbox is None:
        print('dropboxパッケージがインストールされていません')
        return
    dbx = dropbox.Dropbox(dropbox_token)
    for root, dirs, files in os.walk(local_dir):
        for fname in files:
            lpath = os.path.join(root, fname)
            rel = os.path.relpath(lpath, local_dir)
            dpath = os.path.join(dropbox_dir, rel).replace('\\', '/')
            with open(lpath, 'rb') as f:
                dbx.files_upload(f.read(), dpath, mode=dropbox.files.WriteMode.overwrite)
            print(f"Dropboxにアップロード: {dpath}")

def list_dropbox_files(dropbox_token, dropbox_dir):
    if dropbox is None:
        print('dropboxパッケージがインストールされていません')
        return
    dbx = dropbox.Dropbox(dropbox_token)
    res = dbx.files_list_folder(dropbox_dir)
    for entry in res.entries:
        print(entry.path_display)

def download_from_dropbox(dropbox_token, dropbox_path, local_path):
    if dropbox is None:
        print('dropboxパッケージがインストールされていません')
        return
    dbx = dropbox.Dropbox(dropbox_token)
    md, res = dbx.files_download(dropbox_path)
    with open(local_path, 'wb') as f:
        f.write(res.content)
    print(f"Dropboxからダウンロード: {dropbox_path} -> {local_path}")

def main():
    parser = argparse.ArgumentParser(description='履歴/バックアップのDropbox同期')
    subparsers = parser.add_subparsers(dest='cmd')
    up = subparsers.add_parser('upload', help='ディレクトリをDropboxにアップロード')
    up.add_argument('dir', help='アップロードするローカルディレクトリ')
    up.add_argument('--token', required=True, help='Dropboxアクセストークン')
    up.add_argument('--dropbox_dir', required=True, help='Dropbox上の保存ディレクトリ')
    ls = subparsers.add_parser('list', help='Dropbox上のファイル一覧')
    ls.add_argument('--token', required=True, help='Dropboxアクセストークン')
    ls.add_argument('--dropbox_dir', required=True, help='Dropbox上のディレクトリ')
    dl = subparsers.add_parser('download', help='Dropboxからダウンロード')
    dl.add_argument('--token', required=True, help='Dropboxアクセストークン')
    dl.add_argument('--dropbox_path', required=True, help='Dropbox上のパス')
    dl.add_argument('--local_path', required=True, help='保存先ローカルパス')
    args = parser.parse_args()
    if args.cmd == 'upload':
        upload_dir_to_dropbox(args.dir, args.token, args.dropbox_dir)
    elif args.cmd == 'list':
        list_dropbox_files(args.token, args.dropbox_dir)
    elif args.cmd == 'download':
        download_from_dropbox(args.token, args.dropbox_path, args.local_path)
    else:
        print('upload/list/download サブコマンドを指定してください')

if __name__ == '__main__':
    main()
