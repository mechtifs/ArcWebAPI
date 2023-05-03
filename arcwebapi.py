import json
import aiohttp
import asyncio


class Arcaea():
    base_url = 'https://webapi.lowiro.com'

    def __init__(self, email: str, password: str, target_username: str) -> None:
        self.email = email
        self.password = password
        self.target_username = target_username
        self.result = {}
        self.session = None

    def calc_ptt(self, score: int, rating: int) -> float:
        if score >= 10000000:
            return rating+2
        elif score >= 9800000:
            return rating+1+(score-9800000)/200000
        else:
            return max(rating+(score-9500000)/300000, 0)

    async def login(self) -> bool:
        self.session = aiohttp.ClientSession()
        async with self.session.post(self.base_url+'/auth/login', data={
            'email': self.email,
            'password': self.password
        }) as r:
            ret = await r.json()
        if ret.get('isLoggedIn'):
            return True

    async def fetch_score(self, s: dict) -> None:
        songs_url = self.base_url+'/webapi/score/song/friend?song_id={}&difficulty={}&start=0&limit=30'.format(s['sid'], s['difficulty'])
        async with self.session.get(songs_url) as r:
            result = await r.json()
            print(s['sid'], s['difficulty'], result)

            if result['success']:
                for value in result['value']:
                    if value['name'] == self.target_username:
                        if s['sid'] not in self.result:
                            self.result[s['sid']] = {}
                        self.result[s['sid']][s['difficulty']] = {
                            'score': value['score'],
                            'play_point': self.calc_ptt(value['score'], s['rating']/10),
                            'shiny_perfect_count': value['shiny_perfect_count'],
                            'perfect_count': value['perfect_count'],
                            'near_count': value['near_count'],
                            'miss_count': value['miss_count'],
                            'rating': s['rating'],
                            'time_played': value['time_played']
                        }

    async def close_session(self) -> None:
        await self.session.close()

    def get_result(self) -> dict:
        return self.result

async def get_slst() -> dict:
    async with aiohttp.ClientSession() as session:
        async with session.get('https://www.chinosk6.cn/arcscore/get_slst') as r:
            return await r.json()


if __name__ == '__main__':
    email = 'email',
    password = 'password',
    target_username = 'target_username'
    acc = Arcaea(email, password, target_username)
    loop = asyncio.get_event_loop()
    tasks = [loop.create_task(get_slst()), loop.create_task(acc.login())]
    results = loop.run_until_complete(asyncio.wait(tasks))

    if tasks[1].result():
        slst = tasks[0].result()
        tasks = [loop.create_task(acc.fetch_score(s)) for s in slst]
        loop.run_until_complete(asyncio.wait(tasks))
        loop.run_until_complete(acc.close_session())
        with open(f'{target_username}.json', 'w') as f:
            f.write(json.dumps(acc.get_result(), indent=2, ensure_ascii=False))
