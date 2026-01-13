#!/usr/bin/env python3

import uuid, random, asyncio
from bspl.adapter import Adapter
from bspl.adapter.core import COLORS
from configuration import config

import Purchase
from Purchase import Buyer, rfq, quote, accept, reject, deliver

adapter = Adapter(Buyer, Purchase.protocol, config, color=COLORS[0])

deliveries = 0
rejections = 0


async def main():
    for i in range(10):
        msg = rfq(ID=str(uuid.uuid4()), item=random.sample(["ball", "bat"], 1)[0])
        await adapter.send(msg)
        await asyncio.sleep(0.1)


@adapter.reaction(quote)
async def decision(msg):
    if msg["price"] < 50:
        await adapter.send(accept(**msg.payload, address="Home", resp="Accept"))
    else:
        msg = reject(**msg.payload, outcome="Rejected", resp="Reject")
        print(msg)
        global rejections
        rejections += 1
        await adapter.send(msg)


@adapter.reaction(deliver)
async def receive(msg):
    global deliveries
    deliveries += 1
    print(msg)


if __name__ == "__main__":
    adapter.start(main())
    print(
        f"Completed enactments: {rejections + deliveries} "
        + f"({rejections} rejections, {deliveries} deliveries)"
    )
