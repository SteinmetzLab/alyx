import csv
from datetime import datetime, timedelta
from dateutil.rrule import HOURLY
import functools
import io
import logging
from operator import itemgetter
import os.path as op

from django.http import HttpResponse
from django.utils import timezone

import numpy as np


logger = logging.getLogger(__name__)


PALETTE = {
    'green': '#C9FFE2',
    'orange': '#FFE2C9',
    'red': '#FFC9D2',
}


def today():
    return timezone.now().date()


def date(s):
    return datetime.strptime(s, '%Y-%m-%d').date()


def date_range(start_date, end_date):
    for n in range(int((end_date - start_date).days) + 1):
        yield (start_date + timedelta(n))


# Keep the tables in memory instead of reloading the CSV files.
@functools.lru_cache(maxsize=None)
def _get_table(sex):
    sex = 'male' if sex == 'M' else 'female'
    path = op.join(op.dirname(__file__),
                   'static/ref_weighings_%s.csv' % sex)
    with open(path, 'r') as f:
        reader = csv.reader(f)
        d = {int(age): (float(m), float(s))
             for age, m, s in list(reader)}
    return d


def expected_weighing_mean_std(sex, age_w):
    d = _get_table(sex)
    age_min, age_max = min(d), max(d)
    if age_w < age_min:
        return d[age_min]
    elif age_w > age_max:
        return d[age_max]
    else:
        return d[age_w]


def to_weeks(birth_date, dt):
    if not birth_date:
        logger.warning("No birth date specified!")
        return 0
    if not dt:
        return 0
    if isinstance(dt, datetime):
        dt = dt.date()
    return (dt - birth_date).days // 7


def restrict_dates(dates, start, end, *arrs):
    ind = (dates >= start) & (dates <= end)
    return [dates[ind]] + [arr[ind] for arr in arrs]


def find_color(w, e, thresholds):
    """Find the color of a weight, given the expected weight and the list of thresholds."""
    for t, bgc, fgc, ls in thresholds:
        if w < e * t:
            return bgc
    return PALETTE['green']


def return_figure(f):
    buf = io.BytesIO()
    f.savefig(buf, format='png')
    buf.seek(0)
    return HttpResponse(buf.read(), content_type="image/png")


def tzone_convert(date_t, tz):
    date_t = timezone.make_aware(date_t, timezone.get_default_timezone())
    return timezone.make_naive(date_t, tz)


class WaterControl(object):
    def __init__(self, nickname=None, birth_date=None, sex=None,
                 implant_weight=None,
                 reference_weight_pct=0.,
                 zscore_weight_pct=0.,
                 timezone=timezone.get_default_timezone(),
                 ):
        assert nickname, "Subject nickname not provided"
        self.nickname = nickname
        self.birth_date = birth_date
        self.sex = sex
        self.implant_weight = implant_weight or 0.
        self.water_restrictions = []
        self.water_administrations = []
        self.weighings = []
        self.reference_weighing = None
        self.reference_weight_pct = reference_weight_pct
        self.zscore_weight_pct = zscore_weight_pct
        self.thresholds = []
        self.timezone = timezone

    def first_date(self):
        dwa = dwe = None
        if self.water_administrations:
            dwa = min(d for d, _, _ in self.water_administrations).date()
        if self.weighings:
            dwe = min(d for d, _ in self.weighings).date()
        if not dwa and not dwe:
            return self.birth_date
        elif dwa and dwe:
            return min(dwa, dwe)
        elif dwa:
            return dwa
        elif dwe:
            return dwe
        assert 0

    def _check_water_restrictions(self):
        """Make sure all past water restrictions (except the current one) are finished."""
        last_date = None
        for s, e in self.water_restrictions[:-1]:
            if e is None:
                logger.warning(
                    "The water restriction started on %s for %s not finished!",
                    s, self.nickname)
            # Ensure the water restrictions are ordered.
            if last_date:
                assert s >= last_date
            last_date = s

    def add_water_restriction(self, start_date=None, end_date=None):
        """Add a new water restriction."""
        self._check_water_restrictions()
        self.water_restrictions.append((start_date, end_date))

    def end_current_water_restriction(self):
        """If the mouse is under water restriction, end it."""
        self._check_water_restrictions()
        if not self.water_restrictions:
            return
        s, e = self.water_restrictions[-1]
        if e is not None:
            logger.warning("The mouse %s is not currently under water restriction.", self.nickname)
            return
        self.water_restrictions[-1] = (s, today())

    def current_water_restriction(self):
        """Return the date of the current water restriction if there is one, or None."""
        if not self.water_restrictions:
            return None
        s, e = self.water_restrictions[-1]
        return s.date() if e is None else None

    def is_water_restricted(self, date=None):
        """Return whether the subject is currently under water restriction.

        This means the latest water restriction has no end date.

        """
        return self.water_restriction_at(date=date) is not None

    def water_restriction_at(self, date=None):
        """If the subject was under water restriction at the specified date, return
        the start of that water restriction."""
        date = date or today()
        date = date.date() if isinstance(date, datetime) else date
        water_restrictions_before = [
            (s, e) for (s, e) in self.water_restrictions if s.date() <= date]
        if not water_restrictions_before:
            return
        s, e = water_restrictions_before[-1]
        # Return None if the mouse was not under water restriction at the specified date.
        if e is not None and date > e.date():
            return None
        assert e is None or e.date() >= date
        assert s.date() <= date
        return s.date()

    def add_weighing(self, date, weighing):
        """Add a weighing."""
        self.weighings.append((tzone_convert(date, self.timezone), weighing))

    def set_reference_weight(self, date, weight):
        """Set a non-default reference weight."""
        self.reference_weighing = (date, weight)

    def add_water_administration(self, date, volume, hydrogel=False):
        self.water_administrations.append((tzone_convert(date, self.timezone), volume, hydrogel))

    def add_threshold(self, percentage=None, bgcolor=None, fgcolor=None, line_style=None):
        """Add a threshold for the plot."""
        line_style = line_style or '-'
        self.thresholds.append((percentage, bgcolor, fgcolor, line_style))
        self.thresholds[:] = sorted(self.thresholds, key=itemgetter(0))

    def reference_weighing_at(self, date=None):
        """Return the reference weighing at the specified date, or today."""
        if date is None and self.reference_weighing:
            return self.reference_weighing
        date = date or today()
        wr = self.water_restriction_at(date)
        if not wr:
            return
        # Now, wr is the starting date of the water restriction at the specified date.
        # We search the last known weight as this date.
        w = self.last_weighing_before(wr)
        # This is the reference weight.
        return w

    def reference_weight(self, date=None):
        """Return the reference weight at a given date."""
        rw = self.reference_weighing_at(date=date)
        if rw:
            return rw[1]
        return 0.

    def last_weighing_before(self, date=None):
        """Return the last known weight of the subject before the specified date."""
        date = date or today()
        # Sort the weighings.
        self.weighings[:] = sorted(self.weighings, key=itemgetter(0))
        weighings_before = [(d, w) for (d, w) in self.weighings if d.date() <= date]
        if weighings_before:
            return weighings_before[-1]

    def weighing_at(self, date=None):
        """Return the weight of the subject at the specified date."""
        date = date or today()
        weighings_at = [(d, w) for (d, w) in self.weighings if d.date() == date]
        return weighings_at[0][1] if weighings_at else None

    def current_weighing(self):
        """Return the last known weight."""
        return self.last_weighing_before(date=today())

    def weight(self, date=None):
        """Return the current weight."""
        cw = self.last_weighing_before(date=date)
        return cw[1] if cw else 0

    def zscore_weight(self, date=None):
        """Return the expected zscored weight at the specified date."""
        date = date or today()
        rw = self.reference_weighing_at(date=date)
        if not rw:
            return 0
        ref_date, ref_weight = rw
        iw = self.implant_weight
        if not self.birth_date:
            logger.warning("The birth date of %s has not been specified.", self.nickname)
            return 0
        # Age at the time of the reference weighing.
        age_ref = to_weeks(self.birth_date, ref_date)
        age_date = to_weeks(self.birth_date, date)
        # Expected mean/std at that time.
        mrw_ref, srw_ref = expected_weighing_mean_std(self.sex, age_ref)
        # z-score.
        zscore = (ref_weight - iw - mrw_ref) / srw_ref
        # Expected weight.
        mrw_date, srw_date = expected_weighing_mean_std(self.sex, age_date)
        return (srw_date * zscore) + mrw_date + iw

    def expected_weight(self, date=None):
        """Expected weight of the mouse at the specified date, either the reference weight
        if the reference_weight_pct is >0, or the zscore weight."""
        return (self.reference_weight(date=date)
                if self.reference_weight_pct > 0
                else self.zscore_weight(date=date))

    def percentage_weight(self, date=None):
        """Percentage of the weight relative to the expected weight.
        Expected weight is the reference weight or the zscore weight depending on the water
        restriction fields"""
        date = date or today()
        iw = self.implant_weight or 0.
        w = self.weight(date=date)
        e = self.expected_weight(date=date)
        return 100 * (w - iw) / (e - iw) if (e - iw) > 0 else 0.

    def min_weight(self, date=None):
        """Minimum weight for the mouse."""
        date = date or today()
        return (self.zscore_weight(date=date) * self.zscore_weight_pct +
                self.reference_weight(date=date) * self.reference_weight_pct)

    def expected_water(self, date=None):
        """Return the expected water for the specified date."""
        date = date or today()
        iw = self.implant_weight or 0.
        weight = self.last_weighing_before(date=date)
        weight = weight[1] if weight else 0.
        expected_weight = self.expected_weight(date=date) or 0.
        return 0.05 * (weight - iw) if weight < 0.8 * expected_weight else 0.04 * (weight - iw)

    def given_water(self, date=None, hydrogel=None):
        """Return the amount of water given at a specified date."""
        date = date or today()
        return sum(w or 0 for (d, w, h) in self.water_administrations
                   if d.date() == date and (hydrogel is None or h == hydrogel))

    def given_water_liquid(self, date=None):
        """Amount of liquid water given at the specified date."""
        return self.given_water(date=date, hydrogel=False)

    def given_water_hydrogel(self, date=None):
        """Amount of hydrogel water given at the specified date."""
        return self.given_water(date=date, hydrogel=True)

    def given_water_total(self, date=None):
        """Total amount of water given at the specified date."""
        return self.given_water(date=date)

    def remaining_water(self, date=None):
        """Amount of water that remains to be given at the specified date."""
        date = date or today()
        return self.expected_water(date=date) - self.given_water(date=date)

    def excess_water(self, date=None):
        """Amount of water that was given in excess at the specified date."""
        return -self.remaining_water(date=date)

    _columns = ('date', 'weight', 'weighing_at',
                'reference_weight',
                'expected_weight',
                'min_weight',
                'percentage_weight',
                'given_water_liquid',
                'given_water_hydrogel',
                'given_water_total',
                'expected_water',
                'excess_water',
                'is_water_restricted',
                )

    def weight_status(self):
        threshold = max(self.zscore_weight_pct, self.reference_weight_pct)
        thresh_remind = threshold + 0.02
        w = self.percentage_weight()
        if w == 0:
            return 0
        elif (w / 100) < threshold:
            return 2
        elif (w / 100) < thresh_remind:
            return 1
        else:
            return 0

    def to_jsonable(self, start_date=None, end_date=None):
        start_date = date(start_date) if start_date else self.first_date()
        end_date = date(end_date) if end_date else today()
        out = []
        for d in date_range(start_date, end_date):
            obj = {}
            for col in self._columns:
                if col == 'date':
                    obj['date'] = d
                else:
                    obj[col] = getattr(self, col)(date=d)
            out.append(obj)
        # return json.dumps(out, cls=DjangoJSONEncoder)
        return out

    def plot(self, start=None, end=None):
        import matplotlib
        matplotlib.use('AGG')
        import matplotlib.pyplot as plt
        import matplotlib.dates as mpld

        f, ax = plt.subplots(1, 1, figsize=(8, 3))

        # Data arrays.
        if self.weighings:
            loc = mpld.AutoDateLocator(maxticks=8, interval_multiples=False)
            loc.intervald[HOURLY] = [1]
            ax.xaxis.set_major_locator(loc)
            ax.xaxis.set_major_formatter(mpld.DateFormatter('%Y-%m-%d'))

            self.weighings[:] = sorted(self.weighings, key=itemgetter(0))
            weighing_dates, weights = zip(*self.weighings)
            weighing_dates = np.array(weighing_dates, dtype=datetime)
            weights = np.array(weights, dtype=np.float64)
            start = start or weighing_dates.min()
            end = end or weighing_dates.max()
            expected_weights = np.array(
                [self.expected_weight(date) for date in weighing_dates],
                dtype=np.float64)

        # spans is a list of pairs (date, color) where there are changes of background colors.
        for start_wr, end_wr in self.water_restrictions:
            end_wr = end_wr or end
            # Get the dates and weights for the current water restriction.
            ds, ws, es = restrict_dates(
                weighing_dates, start_wr, end_wr, weights, expected_weights)

            # Plot background colors.
            spans = [(start_wr, None)]
            for d, w, e in zip(ds, ws, es):
                c = find_color(w, e, self.thresholds)
                # Skip identical consecutive colors.
                if c == spans[-1][1]:
                    continue
                spans.append((d, c))
            spans.append((end_wr, None))
            for (d0, c), (d1, _) in zip(spans, spans[1:]):
                ax.axvspan(d0, d1, color=c or 'w')

            # Plot weight thresholds.
            for p, bgc, fgc, ls in self.thresholds:
                ax.plot(ds, p * es, ls, color=fgc, lw=2)

            # Plot weights.
            ax.plot(ds, ws, '-ok', lw=2)

        # Axes and legends.
        ax.set_xlim(start, end)
        eq = 'weight > %.1f*ref + %.1f*zscore' % (
            self.reference_weight_pct, self.zscore_weight_pct)
        ax.set_title("Weighings for %s (%s)" % (self.nickname, eq))
        ax.set_xlabel('Date')
        ax.set_ylabel('Weight (g)')
        ax.legend(['%d%%' % (100 * t[0]) for t in self.thresholds], loc=2)
        ax.grid(True)
        f.tight_layout()
        return return_figure(f)


def water_control(subject):
    from actions import models as am
    assert subject is not None
    lab = subject.lab
    # By default, if there is only one lab, use it for the subject.
    if lab is None:
        from misc.models import Lab
        if len(Lab.objects.all()) == 1:
            lab = Lab.objects.first()
    if lab is None:
        logger.warning("Subject %s has no lab, no reference weight percentages considered.",
                       subject)
        rw_pct = zw_pct = 0
    else:
        rw_pct = lab.reference_weight_pct
        zw_pct = lab.zscore_weight_pct

    # Create the WaterControl instance.
    wc = WaterControl(
        nickname=subject.nickname, birth_date=subject.birth_date, sex=subject.sex,
        reference_weight_pct=rw_pct,
        zscore_weight_pct=zw_pct,
        timezone=subject.timezone(),
    )
    wc.add_threshold(percentage=rw_pct or zw_pct, bgcolor=PALETTE['orange'], fgcolor='#FFC28E')
    wc.add_threshold(percentage=.7, bgcolor=PALETTE['red'], fgcolor='#F08699', line_style='--')

    # Water restrictions.
    wrs = am.WaterRestriction.objects.filter(subject=subject).order_by('start_time')
    # Reference weight.
    last_wr = wrs.last()
    if last_wr and last_wr.reference_weight:
        wc.set_reference_weight(last_wr.start_time, last_wr.reference_weight)
    for wr in wrs:
        wc.add_water_restriction(wr.start_time, wr.end_time)

    # Water administrations.
    was = am.WaterAdministration.objects.filter(subject=subject)
    was = was.select_related('water_type').order_by('date_time')
    for wa in was:
        wc.add_water_administration(wa.date_time, wa.water_administered, hydrogel=wa.hydrogel)

    # Weighings
    ws = am.Weighing.objects.filter(subject=subject).order_by('date_time')
    for w in ws:
        wc.add_weighing(w.date_time, w.weight)

    return wc