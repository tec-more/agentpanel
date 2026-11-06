from datetime import datetime, date
from typing import Optional, List, Dict, Any
from tortoise.transactions import atomic
from decimal import Decimal
try:
    from base.plugins.finance.models.account import Account, AccountType
    from base.plugins.finance.models.journal import JournalEntry, JournalLine, JournalStatus
    from base.plugins.finance.models.general_ledger import DailyJournal, GeneralLedger
    from base.plugins.finance.models.trial_balance import TrialBalance, FinancialReport, ReportType
except ImportError:
    Account = None
    AccountType = None
    JournalEntry = None
    JournalLine = None
    JournalStatus = None
    DailyJournal = None
    GeneralLedger = None
    TrialBalance = None
    FinancialReport = None
    ReportType = None


class ReportService:
    model = "report"
    @staticmethod
    async def get_daily_journal(page: int = 1, page_size: int = 20, journal_date_start: Optional[str] = None, 
                                journal_date_end: Optional[str] = None, account_id: Optional[int] = None,
                                period: Optional[str] = None) -> List[DailyJournal]:
        offset = (page - 1) * page_size
        query = DailyJournal.all().order_by("-journal_date", "account_id")
        
        if journal_date_start:
            query = query.filter(journal_date__gte=date.fromisoformat(journal_date_start))
        
        if journal_date_end:
            query = query.filter(journal_date__lte=date.fromisoformat(journal_date_end))
        
        if account_id:
            query = query.filter(account_id=account_id)
        
        if period:
            query = query.filter(period=period)
        
        return await query.offset(offset).limit(page_size)

    @staticmethod
    async def get_daily_journal_count(journal_date_start: Optional[str] = None, journal_date_end: Optional[str] = None, 
                                      account_id: Optional[int] = None, period: Optional[str] = None) -> int:
        query = DailyJournal.all()
        
        if journal_date_start:
            query = query.filter(journal_date__gte=date.fromisoformat(journal_date_start))
        
        if journal_date_end:
            query = query.filter(journal_date__lte=date.fromisoformat(journal_date_end))
        
        if account_id:
            query = query.filter(account_id=account_id)
        
        if period:
            query = query.filter(period=period)
        
        return await query.count()

    @staticmethod
    async def get_general_ledger(page: int = 1, page_size: int = 20, period: Optional[str] = None,
                                 account_id: Optional[int] = None, year: Optional[int] = None,
                                 month: Optional[int] = None) -> List[GeneralLedger]:
        offset = (page - 1) * page_size
        query = GeneralLedger.all().order_by("period", "account_id")
        
        if period:
            query = query.filter(period=period)
        
        if account_id:
            query = query.filter(account_id=account_id)
        
        if year:
            query = query.filter(year=year)
        
        if month:
            query = query.filter(month=month)
        
        return await query.offset(offset).limit(page_size)

    @staticmethod
    async def get_general_ledger_count(period: Optional[str] = None, account_id: Optional[int] = None,
                                       year: Optional[int] = None, month: Optional[int] = None) -> int:
        query = GeneralLedger.all()
        
        if period:
            query = query.filter(period=period)
        
        if account_id:
            query = query.filter(account_id=account_id)
        
        if year:
            query = query.filter(year=year)
        
        if month:
            query = query.filter(month=month)
        
        return await query.count()

    @staticmethod
    async def get_trial_balance(page: int = 1, page_size: int = 20, period: Optional[str] = None,
                                account_type: Optional[str] = None, year: Optional[int] = None,
                                month: Optional[int] = None) -> List[TrialBalance]:
        offset = (page - 1) * page_size
        query = TrialBalance.all().order_by("period", "account_id")
        
        if period:
            query = query.filter(period=period)
        
        if account_type:
            query = query.filter(account__account_type=account_type)
        
        if year:
            query = query.filter(year=year)
        
        if month:
            query = query.filter(month=month)
        
        return await query.offset(offset).limit(page_size)

    @staticmethod
    async def get_trial_balance_count(period: Optional[str] = None, account_type: Optional[str] = None,
                                       year: Optional[int] = None, month: Optional[int] = None) -> int:
        query = TrialBalance.all()
        
        if period:
            query = query.filter(period=period)
        
        if account_type:
            query = query.filter(account__account_type=account_type)
        
        if year:
            query = query.filter(year=year)
        
        if month:
            query = query.filter(month=month)
        
        return await query.count()

    @staticmethod
    @atomic()
    async def generate_trial_balance(year: int, month: int) -> Dict[str, Any]:
        period = f"{year}-{month:02d}"
        
        prev_month = month - 1
        prev_year = year
        if prev_month <= 0:
            prev_month = 12
            prev_year -= 1
        prev_period = f"{prev_year}-{prev_month:02d}"
        
        accounts = await Account.all().order_by("code")
        
        total_debit_balance = Decimal("0.00")
        total_credit_balance = Decimal("0.00")
        total_debit_amount = Decimal("0.00")
        total_credit_amount = Decimal("0.00")
        
        trial_balance_data = []
        
        for account in accounts:
            prev_tb = await TrialBalance.get_or_none(period=prev_period, account=account)
            
            beginning_debit = prev_tb.ending_debit if prev_tb else Decimal("0.00")
            beginning_credit = prev_tb.ending_credit if prev_tb else Decimal("0.00")
            beginning_balance = beginning_debit - beginning_credit
            beginning_balance_type = "debit" if beginning_balance >= 0 else "credit"
            
            lines = await JournalLine.filter(
                journal_entry__period=period,
                journal_entry__status=JournalStatus.POSTED,
                account=account
            )
            
            debit_amount = Decimal("0.00")
            credit_amount = Decimal("0.00")
            
            for line in lines:
                debit_amount += line.debit
                credit_amount += line.credit
            
            ending_debit = beginning_debit + debit_amount
            ending_credit = beginning_credit + credit_amount
            ending_balance = ending_debit - ending_credit
            ending_balance_type = "debit" if ending_balance >= 0 else "credit"
            
            total_debit_balance += ending_debit
            total_credit_balance += ending_credit
            total_debit_amount += debit_amount
            total_credit_amount += credit_amount
            
            existing_tb = await TrialBalance.get_or_none(period=period, account=account)
            if existing_tb:
                await existing_tb.update_from_dict({
                    "beginning_debit": beginning_debit,
                    "beginning_credit": beginning_credit,
                    "beginning_balance": abs(beginning_balance),
                    "beginning_balance_type": beginning_balance_type,
                    "debit_amount": debit_amount,
                    "credit_amount": credit_amount,
                    "ending_debit": ending_debit,
                    "ending_credit": ending_credit,
                    "ending_balance": abs(ending_balance),
                    "ending_balance_type": ending_balance_type,
                })
            else:
                await TrialBalance.create(
                    period=period,
                    year=year,
                    month=month,
                    account=account,
                    beginning_debit=beginning_debit,
                    beginning_credit=beginning_credit,
                    beginning_balance=abs(beginning_balance),
                    beginning_balance_type=beginning_balance_type,
                    debit_amount=debit_amount,
                    credit_amount=credit_amount,
                    ending_debit=ending_debit,
                    ending_credit=ending_credit,
                    ending_balance=abs(ending_balance),
                    ending_balance_type=ending_balance_type,
                    is_leaf=account.is_leaf
                )
            
            trial_balance_data.append({
                "account_id": account.id,
                "account_code": account.code,
                "account_name": account.name,
                "account_type": account.account_type.value,
                "beginning_debit": float(beginning_debit),
                "beginning_credit": float(beginning_credit),
                "beginning_balance": float(abs(beginning_balance)),
                "beginning_balance_type": beginning_balance_type,
                "debit_amount": float(debit_amount),
                "credit_amount": float(credit_amount),
                "ending_debit": float(ending_debit),
                "ending_credit": float(ending_credit),
                "ending_balance": float(abs(ending_balance)),
                "ending_balance_type": ending_balance_type,
            })
        
        return {
            "period": period,
            "year": year,
            "month": month,
            "total_debit_balance": float(total_debit_balance),
            "total_credit_balance": float(total_credit_balance),
            "total_debit_amount": float(total_debit_amount),
            "total_credit_amount": float(total_credit_amount),
            "data": trial_balance_data
        }

    @staticmethod
    async def generate_profit_loss_report(year: int, month: int) -> Dict[str, Any]:
        period = f"{year}-{month:02d}"
        
        revenue_accounts = await Account.filter(account_type=AccountType.INCOME).order_by("code")
        expense_accounts = await Account.filter(account_type=AccountType.EXPENSE).order_by("code")
        
        revenue = Decimal("0.00")
        cost_of_sales = Decimal("0.00")
        operating_expense = Decimal("0.00")
        non_operating_income = Decimal("0.00")
        non_operating_expense = Decimal("0.00")
        
        for account in revenue_accounts:
            lines = await JournalLine.filter(
                journal_entry__period=period,
                journal_entry__status=JournalStatus.POSTED,
                account=account
            )
            for line in lines:
                if "营业外" in account.name:
                    non_operating_income += line.credit
                else:
                    revenue += line.credit
        
        for account in expense_accounts:
            lines = await JournalLine.filter(
                journal_entry__period=period,
                journal_entry__status=JournalStatus.POSTED,
                account=account
            )
            for line in lines:
                if "成本" in account.name:
                    cost_of_sales += line.debit
                elif "营业外" in account.name:
                    non_operating_expense += line.debit
                else:
                    operating_expense += line.debit
        
        gross_profit = revenue - cost_of_sales
        operating_profit = gross_profit - operating_expense
        total_profit = operating_profit + non_operating_income - non_operating_expense
        income_tax = total_profit * Decimal("0.25")
        net_profit = total_profit - income_tax
        
        return {
            "period": period,
            "year": year,
            "month": month,
            "revenue": float(revenue),
            "cost_of_sales": float(cost_of_sales),
            "gross_profit": float(gross_profit),
            "operating_expense": float(operating_expense),
            "operating_profit": float(operating_profit),
            "non_operating_income": float(non_operating_income),
            "non_operating_expense": float(non_operating_expense),
            "total_profit": float(total_profit),
            "income_tax": float(income_tax),
            "net_profit": float(net_profit),
            "report_date": date.today().strftime("%Y-%m-%d")
        }

    @staticmethod
    async def generate_balance_sheet(year: int, month: int) -> Dict[str, Any]:
        period = f"{year}-{month:02d}"
        
        asset_accounts = await Account.filter(account_type=AccountType.ASSET).order_by("code")
        liability_accounts = await Account.filter(account_type=AccountType.LIABILITY).order_by("code")
        equity_accounts = await Account.filter(account_type=AccountType.EQUITY).order_by("code")
        
        assets = {}
        liabilities = {}
        equity = {}
        
        total_assets = Decimal("0.00")
        total_liabilities = Decimal("0.00")
        total_equity = Decimal("0.00")
        
        for account in asset_accounts:
            ending_balance = Decimal("0.00")
            ending_balance_type = "debit"
            
            lines = await JournalLine.filter(
                journal_entry__period=period,
                journal_entry__status=JournalStatus.POSTED,
                account=account
            )
            
            for line in lines:
                ending_balance += line.debit - line.credit
            
            if ending_balance < 0:
                ending_balance_type = "credit"
            
            assets[account.code] = {
                "name": account.name,
                "balance": float(abs(ending_balance)),
                "balance_type": ending_balance_type
            }
            total_assets += abs(ending_balance)
        
        for account in liability_accounts:
            ending_balance = Decimal("0.00")
            ending_balance_type = "credit"
            
            lines = await JournalLine.filter(
                journal_entry__period=period,
                journal_entry__status=JournalStatus.POSTED,
                account=account
            )
            
            for line in lines:
                ending_balance += line.credit - line.debit
            
            if ending_balance < 0:
                ending_balance_type = "debit"
            
            liabilities[account.code] = {
                "name": account.name,
                "balance": float(abs(ending_balance)),
                "balance_type": ending_balance_type
            }
            total_liabilities += abs(ending_balance)
        
        for account in equity_accounts:
            ending_balance = Decimal("0.00")
            ending_balance_type = "credit"
            
            lines = await JournalLine.filter(
                journal_entry__period=period,
                journal_entry__status=JournalStatus.POSTED,
                account=account
            )
            
            for line in lines:
                ending_balance += line.credit - line.debit
            
            if ending_balance < 0:
                ending_balance_type = "debit"
            
            equity[account.code] = {
                "name": account.name,
                "balance": float(abs(ending_balance)),
                "balance_type": ending_balance_type
            }
            total_equity += abs(ending_balance)
        
        return {
            "period": period,
            "year": year,
            "month": month,
            "assets": assets,
            "liabilities": liabilities,
            "equity": equity,
            "total_assets": float(total_assets),
            "total_liabilities": float(total_liabilities),
            "total_equity": float(total_equity),
            "report_date": date.today().strftime("%Y-%m-%d")
        }

    @staticmethod
    async def generate_cash_flow_report(year: int, month: int) -> Dict[str, Any]:
        period = f"{year}-{month:02d}"
        
        prev_month = month - 1
        prev_year = year
        if prev_month <= 0:
            prev_month = 12
            prev_year -= 1
        prev_period = f"{prev_year}-{prev_month:02d}"
        
        cash_accounts = await Account.filter(
            account_type=AccountType.ASSET,
            code__startswith="1001"
        ).order_by("code")
        
        bank_accounts = await Account.filter(
            account_type=AccountType.ASSET,
            code__startswith="1002"
        ).order_by("code")
        
        cash_and_bank = list(cash_accounts) + list(bank_accounts)
        
        cash_beginning_balance = Decimal("0.00")
        cash_ending_balance = Decimal("0.00")
        net_cash_flow = Decimal("0.00")
        
        operating_cash_inflow = Decimal("0.00")
        operating_cash_outflow = Decimal("0.00")
        investing_cash_inflow = Decimal("0.00")
        investing_cash_outflow = Decimal("0.00")
        financing_cash_inflow = Decimal("0.00")
        financing_cash_outflow = Decimal("0.00")
        
        operating_items = []
        investing_items = []
        financing_items = []
        
        revenue_accounts = await Account.filter(account_type=AccountType.INCOME).order_by("code")
        expense_accounts = await Account.filter(account_type=AccountType.EXPENSE).order_by("code")
        asset_accounts = await Account.filter(account_type=AccountType.ASSET).order_by("code")
        liability_accounts = await Account.filter(account_type=AccountType.LIABILITY).order_by("code")
        equity_accounts = await Account.filter(account_type=AccountType.EQUITY).order_by("code")
        
        for account in revenue_accounts:
            lines = await JournalLine.filter(
                journal_entry__period=period,
                journal_entry__status=JournalStatus.POSTED,
                account=account
            )
            for line in lines:
                operating_cash_inflow += line.credit
                operating_items.append({
                    "name": account.name,
                    "type": "inflow",
                    "amount": float(line.credit)
                })
        
        for account in expense_accounts:
            lines = await JournalLine.filter(
                journal_entry__period=period,
                journal_entry__status=JournalStatus.POSTED,
                account=account
            )
            for line in lines:
                operating_cash_outflow += line.debit
                operating_items.append({
                    "name": account.name,
                    "type": "outflow",
                    "amount": float(line.debit)
                })
        
        non_current_assets = await Account.filter(
            account_type=AccountType.ASSET,
            code__startswith="15"
        ).order_by("code")
        
        for account in non_current_assets:
            lines = await JournalLine.filter(
                journal_entry__period=period,
                journal_entry__status=JournalStatus.POSTED,
                account=account
            )
            for line in lines:
                if line.debit > 0:
                    investing_cash_outflow += line.debit
                    investing_items.append({
                        "name": account.name,
                        "type": "outflow",
                        "amount": float(line.debit)
                    })
                if line.credit > 0:
                    investing_cash_inflow += line.credit
                    investing_items.append({
                        "name": account.name,
                        "type": "inflow",
                        "amount": float(line.credit)
                    })
        
        long_term_liabilities = await Account.filter(
            account_type=AccountType.LIABILITY,
            code__startswith="25"
        ).order_by("code")
        
        for account in long_term_liabilities:
            lines = await JournalLine.filter(
                journal_entry__period=period,
                journal_entry__status=JournalStatus.POSTED,
                account=account
            )
            for line in lines:
                if line.credit > 0:
                    financing_cash_inflow += line.credit
                    financing_items.append({
                        "name": account.name,
                        "type": "inflow",
                        "amount": float(line.credit)
                    })
                if line.debit > 0:
                    financing_cash_outflow += line.debit
                    financing_items.append({
                        "name": account.name,
                        "type": "outflow",
                        "amount": float(line.debit)
                    })
        
        for account in equity_accounts:
            lines = await JournalLine.filter(
                journal_entry__period=period,
                journal_entry__status=JournalStatus.POSTED,
                account=account
            )
            for line in lines:
                if line.credit > 0:
                    financing_cash_inflow += line.credit
                    financing_items.append({
                        "name": account.name,
                        "type": "inflow",
                        "amount": float(line.credit)
                    })
        
        for account in cash_and_bank:
            prev_lines = await JournalLine.filter(
                journal_entry__period=prev_period,
                journal_entry__status=JournalStatus.POSTED,
                account=account
            )
            curr_lines = await JournalLine.filter(
                journal_entry__period=period,
                journal_entry__status=JournalStatus.POSTED,
                account=account
            )
            
            prev_balance = Decimal("0.00")
            curr_balance = Decimal("0.00")
            
            for line in prev_lines:
                prev_balance += line.debit - line.credit
            
            for line in curr_lines:
                curr_balance += line.debit - line.credit
            
            cash_beginning_balance += prev_balance
            cash_ending_balance += curr_balance
        
        net_operating_cash = operating_cash_inflow - operating_cash_outflow
        net_investing_cash = investing_cash_inflow - investing_cash_outflow
        net_financing_cash = financing_cash_inflow - financing_cash_outflow
        net_cash_flow = net_operating_cash + net_investing_cash + net_financing_cash
        
        return {
            "period": period,
            "year": year,
            "month": month,
            "cash_beginning_balance": float(cash_beginning_balance),
            "cash_ending_balance": float(cash_ending_balance),
            "net_cash_flow": float(net_cash_flow),
            "operating": {
                "cash_inflow": float(operating_cash_inflow),
                "cash_outflow": float(operating_cash_outflow),
                "net_cash_flow": float(net_operating_cash),
                "items": operating_items
            },
            "investing": {
                "cash_inflow": float(investing_cash_inflow),
                "cash_outflow": float(investing_cash_outflow),
                "net_cash_flow": float(net_investing_cash),
                "items": investing_items
            },
            "financing": {
                "cash_inflow": float(financing_cash_inflow),
                "cash_outflow": float(financing_cash_outflow),
                "net_cash_flow": float(net_financing_cash),
                "items": financing_items
            },
            "report_date": date.today().strftime("%Y-%m-%d")
        }

    @staticmethod
    @atomic()
    async def generate_financial_report(report_type: str, year: int, month: int) -> Dict[str, Any]:
        report_type_enum = ReportType(report_type)
        
        if report_type_enum == ReportType.TRIAL_BALANCE:
            data = await ReportService.generate_trial_balance(year, month)
        elif report_type_enum == ReportType.PROFIT_LOSS:
            data = await ReportService.generate_profit_loss_report(year, month)
        elif report_type_enum == ReportType.BALANCE_SHEET:
            data = await ReportService.generate_balance_sheet(year, month)
        elif report_type_enum == ReportType.CASH_FLOW:
            data = await ReportService.generate_cash_flow_report(year, month)
        else:
            data = {}
        
        report_no = f"RPT{report_type[:3].upper()}{year}{month:02d}{datetime.now().strftime('%d%H%M%S')}"
        
        await FinancialReport.create(
            report_no=report_no,
            report_type=report_type_enum,
            period=f"{year}-{month:02d}",
            year=year,
            month=month,
            report_date=date.today(),
            status="generated",
            data=data,
            remark=f"{report_type_enum.get_label(report_type_enum.value)} {year}年{month}月"
        )
        
        return data