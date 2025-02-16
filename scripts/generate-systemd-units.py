#!/usr/bin/env python3
import argparse
import operator
import os
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Set

SERVICE_PREFIX = "dinkum-"
MYCROFT_TARGET = "dinkum"
SKILLS_TARGET = "skills"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--service",
        action="append",
        default=[],
        nargs=2,
        metavar=("priority", "dir"),
        help="Priority and path to service directory",
    )
    parser.add_argument(
        "--skill", action="append", default=[], help="Path to skill directory"
    )
    parser.add_argument(
        "--venv-dir",
        help="Directory with shared virtual environment (overrides --no-shared-venv)",
    )
    parser.add_argument(
        "--no-shared-venv",
        action="store_true",
        help="Services and skills do not share a virtual environment",
    )
    parser.add_argument(
        "--user",
        required=True,
        help="User to run service as",
    )
    parser.add_argument(
        "--unit-dir",
        default="/etc/systemd/system",
        help="Directory to write unit files",
    )
    args = parser.parse_args()

    if args.venv_dir:
        args.venv_dir = Path(args.venv_dir).absolute()

    if args.skill:
        args.skill = [Path(p).absolute() for p in args.skill]

    config_home = Path("/home") / args.user / ".config"

    # Directory to write systemd unit files
    unit_dir = Path(args.unit_dir)
    unit_dir.mkdir(parents=True, exist_ok=True)

    # Remove previous service files
    for unit_file in unit_dir.glob("dinkum*.*"):
        if unit_file.is_file():
            unit_file.unlink()

    services: Dict[int, Set[str]] = defaultdict(set)
    for priority, service_dir in args.service:
        services[priority].add(service_dir)

    skills_service_path = None
    sorted_services = sorted(services.items(), key=operator.itemgetter(0))
    all_service_ids = set()
    after_services = set()
    skills_after_services = set()
    for priority, service_dirs in sorted_services:
        service_ids = set()
        service_paths = []
        for service_dir in service_dirs:
            service_path = Path(service_dir)
            service_name = service_path.name
            service_path = Path(service_dir)
            service_id = f"{service_path.name}.service"
            if args.venv_dir:
                venv_dir = args.venv_dir
            elif args.no_shared_venv:
                venv_dir = (
                    config_home / "mycroft" / "services" / service_path.name / ".venv"
                )
            else:
                venv_dir = config_home / "mycroft" / ".venv"
            service_paths.append(service_path)
            service_ids.add(service_id)

            with open(
                unit_dir / f"{SERVICE_PREFIX}{service_id}", "w", encoding="utf-8"
            ) as f:
                print("[Unit]", file=f)
                print("Description=", "Mycroft service ", service_id, sep="", file=f)
                print("PartOf=", MYCROFT_TARGET, ".target", sep="", file=f)
                if after_services:
                    print(
                        "After=",
                        " ".join(f"{SERVICE_PREFIX}{id}" for id in after_services),
                        sep="",
                        file=f,
                    )

                print("", file=f)
                print("[Service]", file=f)
                print("Type=notify", file=f)
                print("User=", args.user, sep="", file=f)
                print(
                    "Environment=PYTHONPATH=",
                    service_path.absolute(),
                    sep="",
                    file=f,
                )

                if service_name == SKILLS_TARGET:
                    print(
                        "ExecStart=",
                        venv_dir,
                        "/bin/python -m service ",
                        "--service-id ",
                        service_path.name,
                        " ",
                        sep="",
                        end="",
                        file=f,
                    )
                    for skill_dir in args.skill:
                        print("--skill", skill_dir, "", end="", file=f)

                    print("", file=f)
                else:
                    print(
                        "ExecStart=",
                        venv_dir,
                        "/bin/python -m service ",
                        "--service-id ",
                        service_path.name,
                        sep="",
                        file=f,
                    )
                print("Restart=always", file=f)
                print("RestartSec=10", file=f)
                print("TimeoutStartSec=60", file=f)
                print("WatchdogSec=30", file=f)
                print("StandardOutput=journal", file=f)
                print("StandardError=journal", file=f)

        after_services = service_ids
        all_service_ids.update(service_ids)

    # if args.skill:
    #     assert skills_service_path, f"No service named {SKILLS_TARGET}"
    #     _write_skills_target(
    #         skills_service_path,
    #         args.skill,
    #         skills_after_services,
    #         config_home,
    #         unit_dir,
    #         args.user,
    #         venv_dir=args.venv_dir,
    #         no_shared_venv=args.no_shared_venv,
    #     )

    _write_mycroft_target(all_service_ids, unit_dir)


def _write_mycroft_target(service_ids: Set[str], unit_dir: Path):
    with open(unit_dir / f"{MYCROFT_TARGET}.target", "w", encoding="utf-8") as f:
        print("[Unit]", file=f)
        print("Description=", MYCROFT_TARGET, ".target", sep="", file=f)
        print(
            "Requires=",
            " ".join(f"{SERVICE_PREFIX}{id}" for id in service_ids),
            sep="",
            file=f,
        )
        print("After=graphical.target systemd-user-sessions.service mycroft-xmos.service", file=f)
        print("", file=f)
        print("[Install]", file=f)
        print("WantedBy=mycroft-plasma.service", sep="", file=f)


# def _write_skills_target(
#     skills_service_path: Path,
#     skill_dirs: List[str],
#     after_services: Set[str],
#     config_home: Path,
#     unit_dir: Path,
#     user: str,
#     venv_dir: Optional[Path] = None,
#     no_shared_venv: bool = False,
# ):
#     skill_paths = [Path(d) for d in skill_dirs]
#     skill_ids = {p.name for p in skill_paths}
#     # service_ids = [f"{SERVICE_PREFIX}skill-{id}.service" for id in skill_ids]

#     for skill_path in skill_paths:
#         skill_id = skill_path.name
#         if venv_dir:
#             skill_venv_dir = venv_dir
#         elif no_shared_venv:
#             skill_venv_dir = config_home / "mycroft" / "skills" / skill_id / ".venv"
#         else:
#             skill_venv_dir = config_home / "mycroft" / ".venv"
#         with open(
#             unit_dir / f"{SERVICE_PREFIX}skill-{skill_id}.service",
#             "w",
#             encoding="utf-8",
#         ) as f:
#             print("[Unit]", file=f)
#             print("PartOf=", MYCROFT_TARGET, ".target", sep="", file=f)
#             print("Description=", "Mycroft skill ", skill_id, sep="", file=f)
#             if after_services:
#                 print(
#                     "After=",
#                     " ".join(f"{SERVICE_PREFIX}{id}" for id in after_services),
#                     sep="",
#                     file=f,
#                 )

#             print("", file=f)
#             print("[Service]", file=f)
#             print("Type=notify", file=f)
#             print("User=", user, sep="", file=f)
#             print(
#                 "Environment=PYTHONPATH=",
#                 skills_service_path.absolute(),
#                 sep="",
#                 file=f,
#             )
#             print(
#                 "ExecStart=",
#                 skill_venv_dir,
#                 "/bin/python -m service ",
#                 "--skill-directory '",
#                 skill_path.absolute(),
#                 "' --skill-id '",
#                 skill_id,
#                 "'",
#                 sep="",
#                 file=f,
#             )
#             print("Restart=always", file=f)
#             print("RestartSec=10", file=f)
#             print("TimeoutStartSec=60", file=f)
#             print("WatchdogSec=30", file=f)
#             print("StandardOutput=journal", file=f)
#             print("StandardError=journal", file=f)


if __name__ == "__main__":
    main()
