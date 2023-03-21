from selenium import webdriver
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.keys import Keys
import datetime as dt
import os
import re
import time
import requests
import json
import pandas as pd
import sys
import ast


def main():
    '''
    メインの実行部分
    '''
    # 絞り込み条件
    media_count = 2000
    followers_count = 1000
    ig_user_id = "******************"
    access_token = "******************"
    version = "v9.0"
    
    # ここに検索したいキーワードを入力して下さい。
    keyword_list = ["チーズ"]
    
    # 【一番始めの投稿取得機能】この機能はつけるとAPIの制限にひっかかりやすくなるので、一旦はずす
    # this_year = dt.date.today().strftime('%Y')
    
    # instagram graph apiだとキーワード指定でアカウント検索できないので、次のサイトをキーワードで検索してスクレイピング
    url = 'https://makitani.net/igusersearch/'
    for i, keyword in enumerate(keyword_list):
        print(f'キーワード{keyword}を検索します。')
        driver = account_search(url, keyword)
        
        # メディア数とフォロワー数で条件検索して絞り込んだ結果に対してmediaのtimestampの一番最初のメディアの日時を取得。
        # →その日時を用いて期間で絞り込み（最初の投稿が3カ月以内か？半年以内か？1年以内か？）→これでアカウントがいつから始まったのかを把握できる
        # 一番最初に投稿されたメディアのtimestamp情報を取得するには、afterのキーを使ってページングをする
        
        user_ids = get_user_id(driver)

        df = get_information_on_account(driver, user_ids, version, ig_user_id, access_token, media_count, followers_count, keyword)
        # resultフォルダにデータフレームの出力
        output_result_df(df, keyword)
        print(f'キーワード{keyword}の情報取得終了')
        
        # 【一番始めの投稿取得機能】この機能はつけるとAPIの制限にひっかかりやすくなるので、一旦はずす
        # after_key_get(account_dict)
        
        # リストの最後までキーワードを検索し終わった場合は終了
        if len(keyword_list) == i + 1:
            print("全キーワードの情報取得が終わったのでプログラムを終了します。")
            sys.exit()
        else:
            # API制限回避のため30分スリープ
            time.sleep(60*30)
    
    
def after_key_get(account_dict):
    '''
    ページ送りのafter_keyを出力する
    '''
    after_key = []
    try:
        after_key = account_dict['business_discovery']['media']['paging']['cursors']['after']
        # print(after_key)
        return after_key
    except KeyError:
        # print('after_key', e)
        return after_key


def pagenate(user_id, after_key, version, ig_user_id, access_token):
    '''
    ユーザー名とafter_keyを受け取りAPIリクエストによりページ送りする
    '''
    api_pagenation = f'https://graph.facebook.com/{version}/{ig_user_id}?fields=business_discovery.username({user_id}){{media.after({after_key}).limit(1000){{timestamp}}}}&access_token={access_token}'
    r = requests.get(api_pagenation)
    pagenate_dict = json.loads(r.content)    
    
    return pagenate_dict
        

def account_search(url, keyword):
    '''
    サイトにアクセスして
    アカウントを検索
    '''
    driver = webdriver.Chrome(ChromeDriverManager().install())
    driver.get(url)

    input_element = driver.find_element_by_id('gsc-i-id1')
    input_element.clear()
    input_element.send_keys(keyword)
    input_element.send_keys(Keys.RETURN)
    time.sleep(1)
    
    return driver


def get_user_id(driver):
    '''
    ページからページネーションしながらURLを取得し、user_idをリストにまとめる
    '''

    # まずページからアカウントのurl情報を得る
    
    i = 2
    urls = []
    user_ids = []

    while True:
        # urlを収集
        url_objects = driver.find_elements_by_css_selector('div.gsc-thumbnail-inside > div > a')
        # もしurlのリストが存在するなら
        if url_objects:
            for object in url_objects:
                urls.append(object.get_attribute('href'))
        # urlのリストが存在しない場合 -> ページが終わった可能性あり
        else:
            print('URLが取得できませんでした。')
            
        filtered_urls = filter(None, urls)
        urls = list(filtered_urls)
                                        
        # ページ送りを試す
        try:
            driver.find_element_by_css_selector(f'div.gsc-cursor-box.gs-bidi-start-align > div > div:nth-child({i})').click()
            
            # 【一番始めの投稿取得機能】この機能はつけるとAPIの制限にひっかかりやすくなるので、一旦はずす
            #  after_key_get(account_dict)
            time.sleep(1)
        
            print('次のページに行きます。')
        except Exception:
            print('ページがなくなりました')
            break
        i += 1
    driver.quit()
        
    # アカウントのurlリストからuser_idの部分を取得　m.group(1)
    user_ids = [re.search(r'https://www.instagram.com/(.*?)/', text).group(1) for text in urls if re.search(r'https://www.instagram.com/(.*?)/', text)]
    user_ids = list(set(user_ids))

    return user_ids


def get_information_on_account(driver, user_ids, version, ig_user_id, access_token, media_count, followers_count, keyword):
    '''
    APIリクエストを送ってアカウント情報を取得して、
    アカウント情報を条件で絞り込む
    '''
    account_dict = []
    df = pd.DataFrame()
    for user_id in user_ids:
        
        # APIにGETリクエストを投げて、アカウントごとに次の情報をJsonで取得 →　username, website, name, ig_id, id, profile_picture_url, biography, follows_count,followers_count, media_count, mediaのtimestamp
        api_point = f'https://graph.facebook.com/{version}/{ig_user_id}?fields=business_discovery.username({user_id}){{username, website, name, id, profile_picture_url, biography, follows_count,followers_count, media_count, media{{timestamp, like_count, comments_count, caption}}}}&access_token={access_token}'

        r = requests.get(api_point)
        account_dict = json.loads(r.content)
        df1 = pd.json_normalize(account_dict)
        
        # API制限にひっかかった場合
        try:
            if account_dict['error']['code'] == 4:
                print('APIリミットに達しました。1時間後に再度試してみて下さい。')
                driver.quit()
                dt_now = dt.datetime.now()
                print(dt_now, '1時間待機します。')
                time.sleep(60*60)
                print(dt_now, '再度APIリクエストを送ります。')
                continue
        except Exception:  # キーエラー=account_dict['error']['type']がない場合
            pass

        # ここから条件指定での絞り込み
        try:
            # まずメディア数とフォロワー数で条件検索してアカウントを絞り込む
            if df1.get('business_discovery.media_count')[0] <= media_count and df1.get('business_discovery.followers_count')[0] >= followers_count:

                # メディア数とフォロワー数で条件指定されたアカウントの出力
                df = pd.concat([df, df1], ignore_index=True)
                
                continue
                # 【一番始めの投稿取得機能】この機能はつけるとAPIの制限にひっかかりやすくなるので、一旦コメントアウト
                
                # after_key = after_key_get(account_dict)  # ページ送りのafter_keyを取得
                # page_nate_dict = pagenate(user_id, after_key, version, ig_user_id, access_token)
                # timestamp = page_nate_dict['business_discovery']['media']['data'][-1]['timestamp']  # ページ送り後の最後尾のタイムスタンプ取得
                # m = re.search('((\d{4})-\d{2}-\d{2}).*', timestamp)  #　
                # 最後のタイムスタンプから西暦m.group(2)を取得（文字列）
                
                # もしも西暦が今年ならば
                # if m.group(2) == dt.date.today().strftime('%Y'):
                    # print(f'今年メディア数が{media_count}以下でフォロワー数{followers_count}人を達成したアカウント情報はこちら')
                    # print(account_dict)
                    
                # else:
                    # continue
            else:
                continue
            
        except Exception:
            pass
            # ビジネスアカウントやプロアカウントじゃない人だった場合はAPIでユーザー情報取得ができない
            # print('ユーザーが存在しませんでした。')
            continue
    return df


# keyword = '英会話'

# today = dt.datetime.today()
# today_csv = today.strftime("%Y-%m-%d.csv")
# # df = pd.read_csv(f'./csvdata/フルーツ_2020-12-21.csv')
# df = pd.read_csv(f'./csvdata/{keyword}_{today_csv}')

def output_result_df(df, keyword):
    # 全てのカラム名をリネーム 列の場所がコロコロ移動するので、列名でリネーム
    df = df.rename(columns={'Unnamed: 0': 'index', 'business_discovery.username': 'username', 'business_discovery.name': 'name', 'business_discovery.id': 'id2', 'business_discovery.profile_picture_url': 'prof_url', 'business_discovery.biography': 'biography', 'business_discovery.follows_count': 'follows', 'business_discovery.followers_count': 'followers', 'business_discovery.media_count': 'medias', 'business_discovery.media.data': 'media', 'business_discovery.media.paging.cursors.after': 'after', 'business_discovery.website': 'web'})

    # 特定の列の出力　リストのネスト
    df = df[['username', 'web', 'name', 'biography', 'follows', 'followers', 'medias', 'media']]

    df.to_csv('zakka.csv', encoding='utf_8_sig')

    df['FF比'] = round(100 * df['follows']/df['followers'])
    df['1投稿ごとのfollower増'] = round(df['followers']/df['medias'])
    df['url'] = 'https://www.instagram.com/' + df['username']

    # CSVからデータフレームを読み込んだ際にリストが文字列になってしまう不具合を解消
    # df['media'] = [ast.literal_eval(d) for d in df['media']]

    # アカウントごとの平均いいね数とコメント数を求める関数
    def like_comment(num):
        #media_list = df['media'][num]
        sum_likes = 0
        sum_comments = 0
        for i in range(len(df['media'][num])):
            sum_likes += df['media'][num][i]['like_count']
            sum_comments += df['media'][num][i]['comments_count']
        return sum_likes/len(df['media'][num]), sum_comments/len(df['media'][num])

    # 平均いいね数とコメント数を求めてdfの列に追加
    data = [like_comment(num) for num in range(len(df['media']))]
    df2 = pd.DataFrame(data, columns=['平均いいね数', '平均コメント数'])

    df['平均いいね数'] = df2['平均いいね数']
    df['平均コメント数'] = df2['平均コメント数']

    # 最終投稿日を求めてdfの列に追加
    last_date_list = []

    for i in range(df.shape[0]):
        text = df['media'][i][0]['timestamp']
        last_date_list.append(re.search('\d{4}-\d{2}-\d{2}', text).group())
    df['最終投稿日'] = last_date_list

    # アカウントごとのエンゲージメント率を求める
    engage_list = []
    for i in range(df.shape[0]):
        engage_list.append(round(100 * df['平均いいね数'][i]/df['followers'][i]))
    engage_list
    df['エンゲージメント率'] = engage_list

    df3 = df.sort_values('1投稿ごとのfollower増', ascending=False)

    # データの保存
    dirname = 'resultdata'
    if not os.path.isdir(dirname):
        os.mkdir(dirname)
    # resultdataフォルダにCSVデータ出力
    today = dt.datetime.today()
    filename = keyword + '_' + today.strftime("%Y-%m-%d.csv")
    df3.to_csv(os.path.join(dirname, filename), encoding='utf-8-sig')

    df3.drop('media', axis=1)


if __name__ == '__main__':
    main()