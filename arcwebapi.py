import json
import aiohttp
import asyncio


class Arcaea():
    base_url = 'https://webapi.lowiro.com'

    def __init__(self, email: str, password: str) -> None:
        self.email = email
        self.password = password
        self.loop = None
        self.session = None
        self.is_logged_in = False
        self.friend_ids = set()

    def calc_ptt(self, score: int, rating: int) -> float:
        if score >= 10000000:
            return rating+2
        elif score >= 9800000:
            return rating+1+(score-9800000)/200000
        else:
            return max(rating+(score-9500000)/300000, 0)

    async def login(self) -> None:
        async with self.session.post(self.base_url+'/auth/login', data={'email': self.email, 'password': self.password}) as r:
            resp = await r.json()
            self.is_logged_in = resp.get('isLoggedIn')

    async def fetch_play_info(self, song: dict, user_id: int) -> dict:
        songs_url = self.base_url+'/webapi/score/song/friend?song_id={}&difficulty={}&start=0&limit=30'.format(song['sid'], song['difficulty'])
        async with self.session.get(songs_url) as r:
            result = await r.json()

            if result['success']:
                for value in result['value']:
                    if value['user_id'] == user_id:
                        value.update(song)
                        return value

    async def fetch_recent_play_info(self, user_id: int) -> dict:
        async with self.session.get(self.base_url+'/webapi/user/me') as r:
            result = await r.json()

            if result['success']:
                for friend in result['value']['friends']:
                    if friend['user_id'] == user_id:
                        return friend['recent_score'][0]

    async def add_friend(self, user_code: str) -> dict:
        async with self.session.post(
            self.base_url+'/webapi/friend/me/add',
            headers={'Content-Type': 'multipart/form-data; boundary=boundary'},
            data=f'--boundary\r\nContent-Disposition: form-data; name=\"friend_code\"\r\n\r\n{user_code}\r\n--boundary--\r\n') as r:
            return await r.json()

    async def del_friend(self, user_id: int) -> dict:
        async with self.session.post(
            self.base_url+'/webapi/friend/me/delete',
            headers={'Content-Type': 'multipart/form-data; boundary=boundary'},
            data=f'--boundary\r\nContent-Disposition: form-data; name=\"friend_id\"\r\n\r\n{user_id}\r\n--boundary--\r\n') as r:
            return await r.json()

    async def update_friend_list(self) -> None:
        async with self.session.get(self.base_url+'/webapi/user/me') as r:
            resp = await r.json()
            self.friend_ids = set([f['user_id'] for f in resp['value']['friends']])

    async def get_slst(self) -> dict:
        async with aiohttp.ClientSession() as session:
            async with session.get('https://www.chinosk6.cn/arcscore/get_slst') as r:
                return await r.json()

    async def open_session(self) -> None:
        self.session = aiohttp.ClientSession()

    def close_session(self) -> None:
        self.loop.run_until_complete(self.loop.create_task(self.session.close()))

    def get_user_id(self, user_code: str) -> None:
        if not self.loop:
            self.loop = asyncio.get_event_loop()

            self.loop.run_until_complete(self.loop.create_task(self.open_session()))

        if not self.is_logged_in:
            self.loop.run_until_complete(self.loop.create_task(self.login()))

            if not self.is_logged_in:
                print('Login failed!')
                return

        self.loop.run_until_complete(self.loop.create_task(self.update_friend_list()))
        self.loop.run_until_complete(asyncio.wait([self.loop.create_task(self.del_friend(user_id)) for user_id in self.friend_ids]))

        task = self.loop.create_task(self.add_friend(user_code))
        self.loop.run_until_complete(task)
        resp = task.result()

        if resp.get('success'):
            return resp['value']['friends'][0]['user_id']
        elif resp.get('error_code') == 401:
            print('User not found!')
            return

    def fetch_all(self, user_code: str) -> dict:
        user_id = self.get_user_id(user_code)

        task = self.loop.create_task(self.get_slst())
        self.loop.run_until_complete(task)
        slst = task.result()

        tasks = [self.loop.create_task(self.fetch_play_info(song, user_id)) for song in slst]
        self.loop.run_until_complete(self.loop.create_task(asyncio.wait(tasks)))

        result = {}
        for t in tasks:
            r = t.result()
            if r:
                if r['sid'] not in result:
                    result[r['sid']] = {}
                result[r['sid']][r['difficulty']] = {
                    'score': r['score'],
                    'play_point': self.calc_ptt(r['score'], r['rating']/10),
                    'best_clear_type': r['best_clear_type'],
                    'shiny_perfect_count': r['shiny_perfect_count'],
                    'perfect_count': r['perfect_count'],
                    'near_count': r['near_count'],
                    'miss_count': r['miss_count'],
                    'rating': r['rating'],
                    'time_played': r['time_played']
                }

        return result

    def fetch_recent(self, user_code: str) -> dict:
        user_id = self.get_user_id(user_code)

        task = self.loop.create_task(self.get_slst())
        self.loop.run_until_complete(task)
        slst = task.result()

        task = self.loop.create_task(self.fetch_recent_play_info(user_id))
        self.loop.run_until_complete(task)
        r = task.result()

        result = {
            'song_id': r['song_id'],
            'score': r['score'],
            'difficulty': r['difficulty'],
            'play_point': r['rating'],
            'shiny_perfect_count': r['shiny_perfect_count'],
            'perfect_count': r['perfect_count'],
            'near_count': r['near_count'],
            'miss_count': r['miss_count'],
            'rating': r['rating'],
            'time_played': r['time_played']
        }

        for song in slst:
            if song['sid'] == r['song_id'] and song['difficulty'] == r['difficulty']:
                result['rating'] = song['rating']
                break

        return result


if __name__ == '__main__':
    email = 'email',
    password = 'password',
    user_code = 'user_code'
    acc = Arcaea(email, password)

    result = acc.fetch_all(user_code)
    with open(f'{user_code}.json', 'w') as f:
        f.write(json.dumps(result, indent=2, ensure_ascii=False))

    result = acc.fetch_recent(user_code)
    with open(f'{user_code}_r1.json', 'w') as f:
        f.write(json.dumps(result, indent=2, ensure_ascii=False))

    acc.close_session()
