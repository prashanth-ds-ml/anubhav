---
name: plan-a-truck
description: Plan one order or one day as reversible drafts - find the site and orders, pick a vehicle that fits every rule, check it, then draft.
---
# Plan a truck

Use this for "plan a truck for …", "load ki bandi pettu", or "plan tomorrow".

1. **Find the place and the orders.** `find_site` for the name the person used (nicknames may be in your lessons). Then
   `list_open_orders` for that site and date. For a whole day or many orders, start with `plan_board`: it groups orders
   by site with each site's limits, distance and learned rules, and lists the free vehicles.
2. **Read the site's limits before choosing.** `get_site_constraints`, and every approved lesson about this site
   (gate length, receiving hours, weekly off, night-only). An approved rule is a hard limit; advice is a preference.
3. **Choose the vehicle.** Only vehicles free that day (`list_vehicles` with `available_on`). It must fit the load (kg and
   m3), the site's limits and the lessons. Prefer the smallest vehicle that fits; say why you rejected a bigger one.
4. **Check before you draft.** `check_load` with the assignment. If any check fails, change the vehicle or split the
   load; never draft something a check refused.
5. **Draft, never dispatch.** `create_dispatch_draft` (or `create_dispatch_drafts` for several). A draft holds the
   vehicle and waits for a person.
6. **Reply** in the person's language: the vehicle and why, the checks that passed, the lessons you followed (by id),
   anything you could not check, and that it is a draft only.

If the site or the order is ambiguous, ask one short question instead of guessing.
