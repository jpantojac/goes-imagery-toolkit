# Contributing to GOES Imagery Toolkit 🌍

Thank you for your interest in contributing to **GOES Imagery Toolkit**! We welcome community contributions, bug reports, feature enhancements, and scientific improvements.

---

## 📋 Code of Conduct
Please maintain a respectful, constructive, and inclusive tone across all discussions, issues, and pull requests.

---

## 🛠️ How to Contribute

### 1. Reporting Issues
* Search existing issues to verify if the bug or feature request has already been reported.
* When opening a new issue, please include:
  * Operating System and Python version.
  * Dependency environment details (Conda, Docker, or native pip).
  * Exact command executed and full traceback.
  * Expected vs. actual behavior.

### 2. Pull Request Workflow
1. **Fork** the repository and clone your fork locally:
   ```bash
   git clone https://github.com/<your-username>/goes-imagery-toolkit.git
   cd goes-imagery-toolkit
   ```
2. Create a feature branch:
   ```bash
   git checkout -b feature/my-enhancement
   ```
3. Set up the Conda environment:
   ```bash
   conda env create -f environment.yml
   conda activate goes
   ```
4. Implement your changes following **PEP 8** style guidelines and type annotations.
5. Ensure tests pass before opening a PR:
   ```bash
   python -m unittest discover tests
   ```
6. Commit using clear, conventional commit messages:
   ```bash
   git commit -m "feat: add support for GOES mesoscale sectors"
   ```
7. Push to your branch and open a **Pull Request** against `main`.

---

## 🔬 Scientific and Data Integrity
When modifying radiometric calibration equations, Planck coefficients ($fk_1, fk_2, bc_1, bc_2$), or projection transformations, please cite relevant NOAA/NESDIS ABI ATBD (Algorithm Theoretical Basis Document) specifications or peer-reviewed literature in the pull request description.

---

## 📄 License
By contributing, you agree that your contributions will be licensed under the project's [MIT License](LICENSE).

