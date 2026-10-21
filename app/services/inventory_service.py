from .constants import GRADES, SUBS, STYLES

def initial_state():
    walls = [dict(id=f"w{i}", name=name, angle=angle) for i, (name, angle) in enumerate(
        [("Slab Wall", -10), ("Main Wall", 0), ("Comp Wall", 20), ("Cave", 55)], 1)]
    climbs = []
    for i, wall in enumerate(walls):
        for j in range([8, 12, 10, 7][i]):
            climbs.append(dict(id=f"c{len(climbs)+1}", wallId=wall["id"],
                               grade=GRADES[(j*3+i*2) % 9], sub=SUBS[(j+i) % 3],
                               style=STYLES[(j+i*2) % len(STYLES)], status="Active"))
    return dict(walls=walls, climbs=climbs,
                gradeTargets={g: [max(1, 3-i//4), max(1, 3-i//5), max(1, 2-i//4)] for i,g in enumerate(GRADES)},
                styleTargets={s:7 for s in STYLES}, selected=["w1", "w3"],
                newCounts={"w1":5, "w3":5}, plan=[])
