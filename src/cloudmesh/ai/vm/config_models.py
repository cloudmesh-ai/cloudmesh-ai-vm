from dataclasses import dataclass, field
from typing import Dict, Any, Optional

@dataclass
class ProviderConfig:
    name: str
    enabled: bool = True
    image: Optional[str] = None
    size: Optional[str] = None
    flavor: Optional[str] = None
    cpus: Optional[int] = None
    memory: Optional[str] = None
    disk: Optional[str] = None
    auth: Optional[str] = None
    project_name: Optional[str] = None
    site: Optional[str] = None
    security_group: Optional[str] = None
    access_key: Optional[str] = None
    secret_key: Optional[str] = None
    region: Optional[str] = None
    tenant_id: Optional[str] = None
    subscription_id: Optional[str] = None
    client_id: Optional[str] = None
    client_secret: Optional[str] = None
    project_id: Optional[str] = None
    private_key: Optional[str] = None
    distro: Optional[str] = None
    ssh_link: Optional[bool] = None

    @classmethod
    def from_dict(cls, name: str, data: Dict[str, Any]):
        # Remove 'name' from data if it's present to avoid duplicate keyword argument
        filtered_data = {k: v for k, v in data.items() if k != 'name' and k in cls.__dataclass_fields__}
        return cls(name=name, **filtered_data)

@dataclass
class GlobalConfig:
    username: str
    counter: int
    default_cloud: str
    clouds: Dict[str, ProviderConfig] = field(default_factory=dict)
    last_vm: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]):
        clouds_data = data.get("clouds", {})
        clouds = {name: ProviderConfig.from_dict(name, cfg) for name, cfg in clouds_data.items()}
        return cls(
            username=data.get("username", "user"),
            counter=data.get("counter", 0),
            default_cloud=data.get("default_cloud", ""),
            clouds=clouds,
            last_vm=data.get("last_vm")
        )
