## Commit and push the inner repository (parker_turntable)

```
cd parker_turntable
git add .
git commit -m "Describe changes made inside parker_turntable"
git push

```
## move to outer repo

```
cd ..
```


## Stage, commit, and push the outer repository
```
git add .
git commit -m "Describe outer repo changes and update parker_turntable pointer"
git push
```


### Why the order matters
If you push the outer repository before pushing parker_turntable, your outer repo on GitHub will point to a commit hash that only exists on your local machine—causing errors for anyone else (or a CI/CD pipeline) trying to pull or clone the project.

### Submodule Cloning
When pulling future updates on another machine, run git pull --recurse-submodules to update both the outer repo and the inner submodule pointer at the same time