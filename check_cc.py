import colorcet as cc
print(f"Fire[0]: {cc.fire[0]}", flush=True)
print(f"Fire[128]: {cc.fire[128]}", flush=True)

# Check for Aliases
print("Fire alias exists:", hasattr(cc, 'fire'), flush=True)
print("Rainbow alias exists:", hasattr(cc, 'rainbow'), flush=True)
print("BKR alias exists:", hasattr(cc, 'bkr'), flush=True)
print("Colorwheel alias exists:", hasattr(cc, 'colorwheel'), flush=True)
