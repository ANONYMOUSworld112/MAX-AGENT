import asyncio

async def process_item(item):
    await asyncio.sleep(0.001)
    return f'processed_{item}'

async def run_worker():
    q = asyncio.Queue()
    for i in range(3):
        await q.put(i)
    results = []
    while not q.empty():
        item = await q.get()
        res = await process_item(item)
        results.append(res)
        q.task_done()
    return results

if __name__ == '__main__':
    res = asyncio.run(run_worker())
    print(f'Done {len(res)} items')
