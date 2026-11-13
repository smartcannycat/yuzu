"""Read public Farpost listing pages and validate compatible local parts."""

from dataclasses import dataclass


class FarpostFetchError(RuntimeError):
    """Source failed, blocked the request or returned unrecognized markup."""


@dataclass(frozen=True)
class PartCriteria:
    make: str
    model: str
    body_code: str
    panel_id: str
    part_name: str
    side: str = ""
    position: str = ""
    paint_code: str = ""

    @property
    def query(self) -> str:
        return " ".join(
            filter(
                None,
                (
                    self.make,
                    self.model,
                    self.body_code,
                    self.part_name,
                    self.side,
                    self.position,
                    self.paint_code,
                ),
            )
        )


@dataclass(frozen=True)
class PartOffer:
    offer_id: str
    url: str
    title: str
    price_rub: int
    color_matched: bool
