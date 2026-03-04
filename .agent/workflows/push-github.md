---
description: Push all local changes to GitHub (stage, commit with message, push to main)
---

## Prerequisites
- Git is installed and configured
- Remote `origin` is set to `https://github.com/prasannabme2022/Medtrack.git`
- User is in the medtrack project directory

## Steps

1. Check which files have changed
```bash
git -C "c:\Users\every\.gemini\antigravity\playground\holographic-ring\medtrack" status
```

2. Stage all changed and new files
```bash
git -C "c:\Users\every\.gemini\antigravity\playground\holographic-ring\medtrack" add -A
```

3. Commit with a descriptive message (user will be prompted or provide one)
```bash
git -C "c:\Users\every\.gemini\antigravity\playground\holographic-ring\medtrack" commit -m "chore: update MedTrack application"
```

// turbo
4. Push to the main branch on GitHub
```bash
git -C "c:\Users\every\.gemini\antigravity\playground\holographic-ring\medtrack" push origin main
```

// turbo
5. Confirm the push succeeded
```bash
git -C "c:\Users\every\.gemini\antigravity\playground\holographic-ring\medtrack" log --oneline -5
```

## Expected Output
```
To https://github.com/prasannabme2022/Medtrack.git
   XXXXXXX..YYYYYYY  main -> main
```
