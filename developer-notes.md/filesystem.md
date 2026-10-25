# Navigating the Filesystem in Bash

For those coming from a Windows background, the Linux filesystem can feel foreign. In this guide, we will cover the essential concepts and commands needed to navigate and manage files and directories within your Multipass VMs.

## 1. The Core Rule: Case Sensitivity

The most important thing to understand about the Linux filesystem is that **it is case-sensitive**.

In Windows, `MyFile.txt` and `myfile.txt` are generally seen as the same file. In Linux, they are **two completely different files**.

- `Project/` $\neq$ `project/`
- `README.md` $\neq$ `readme.md`
- `Sudo` $\neq$ `sudo` (Note: almost all Linux commands, like `ls`, `cd`, and `sudo`, are lowercase).

**Tip**: To avoid errors and confusion, the industry standard is to use **lowercase** for all filenames and directory names, using underscores (`_`) or hyphens (`-`) instead of spaces.

---

## 2. Understanding the Hierarchy

Linux uses a single-tree structure starting from the **Root**.

- **`/` (Root)**: The top-level directory. Everything on the system lives under here.
- **`/home/username`**: Your personal space. This is where you should store all your projects.
- **`~` (Tilde)**: A shortcut for your current user's home directory (e.g., `cd ~` takes you home).
- **`/etc`**: Contains system-wide configuration files (e.g., `/etc/hosts`, `/etc/ssh/sshd_config`).
- **`/var/log`**: Where the system and applications store their log files.
- **`/tmp`**: Temporary files that are usually cleared upon reboot.

---

## 3. Essential Command Examples

### Navigation
| Command | Description | Example |
| :--- | :--- | :--- |
| `pwd` | **P**rint **W**orking **D**irectory | `pwd` $\rightarrow$ `/home/ubuntu/work` |
| `ls` | **L**i**s**t files | `ls -la` (List all files, including hidden, in long format) |
| `cd` | **C**hange **D**irectory | `cd ~/work/project1` (Move to project1) |
| `cd ..` | Move up one level | `cd ..` (Move from `/home/ubuntu/work` to `/home/ubuntu`) |

### File & Folder Manipulation
| Command | Description | Example |
| :--- | :--- | :--- |
| `mkdir` | **M**a**k**e **Dir**ectory | `mkdir my_project` |
| `touch` | Create empty file | `touch notes.txt` |
| `cp` | **C**o**p**y | `cp source.txt backup.txt` |
| `mv` | **M**o**v**e or Rename | `mv old_name.txt new_name.txt` |
| `rm` | **R**e**m**ove file | `rm temp.txt` |
| `rm -rf` | Force remove directory | `rm -rf old_folder/` (**Warning**: Deletes everything permanently) |

### Viewing Content
| Command | Description | Example |
| :--- | :--- | :--- |
| `cat` | Print entire file | `cat config.yaml` |
| `less` | View file page-by-page | `less large_log.txt` (Press `q` to quit) |
| `head` | View first 10 lines | `head -n 5 file.txt` (View first 5 lines) |
| `tail` | View last 10 lines | `tail -f /var/log/syslog` (Follow log in real-time) |

---

## 4. Absolute vs. Relative Paths

Understanding paths is critical for automation scripts and Makefiles.

### Absolute Path
Starts from the root `/`. It is the "full address" of the file.
- Example: `/home/ubuntu/work/project/main.py`
- **Pros**: Works from anywhere in the system.

### Relative Path
Starts from where you currently are (`pwd`).
- Example: If you are in `~/work`, the relative path to `main.py` is `project/main.py`.
- **Pros**: Shorter and makes your project folders portable.

---

## 5. Practical Exercise: Creating a Project Structure

Try running these commands in your terminal to practice:

```bash
# 1. Go home and create a work folder
cd ~
mkdir -p work/lab_exercise

# 2. Enter the folder
cd work/lab_exercise

# 3. Create a few files
touch README.md requirements.txt main.py

# 4. Create a subfolder for data
mkdir data

# 5. Move a file into that folder
touch data/sample.csv

# 6. List everything to verify (using -R for recursive)
ls -R
```

### Summary Checklist
- [ ] I remember that `File.txt` and `file.txt` are different.
- [ ] I can navigate to my home directory using `~`.
- [ ] I know how to create, move, and delete files/folders.
- [ ] I understand the difference between `/home/ubuntu/file` (absolute) and `file` (relative).