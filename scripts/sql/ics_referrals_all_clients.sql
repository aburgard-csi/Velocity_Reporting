/*  ICS branch referrals for every ICS client, one row per referred account.

    Based on "Referred Accounts.sql" (one client, run inside that client's a<client_id> database).
    This version runs from any database: it finds the ICS clients in the central referral view,
    then reads each client's own a<client_id> database for the account, spend and balance detail.

    Settings:
      @since         only referrals issued on or after this date (null = all history)
      @opened_only   1 = only referrals that opened an account (the original query's filter),
                     0 = every referral, with account_found = 'N' where no account matched
      @client_list   leave empty for every client with branch referrals, or list client ids

    Changes from the original:
      * @client_name was declared varchar with no length, which SQL Server treats as varchar(1),
        so the printed name was one character. Sizes are explicit here.
      * The original's LEFT JOIN to accounts became an inner join through
        "accounts.date_opened is not null"; that is now the @opened_only switch.
      * The per-account history aggregate and the latest-balance lookup read the client's own
        database, so one run covers every client. A client with no a<client_id> database is
        skipped and printed.
      * Output carries member names (name1). Keep results on CSI systems.
*/
set nocount on;

declare @since date = null;          -- e.g. '2025-09-01'
declare @opened_only bit = 0;
declare @client_list table (client_id int primary key);
-- insert @client_list values (1075), (1509), (1537), (1632), (1676), (1705), (1776);

declare @clients table (client_id int primary key, client_name varchar(200));

insert @clients (client_id, client_name)
select distinct c.client_id, c.name
from MRDB..MIGRATION.GETICREFERRALSVIEWPLUSMEMO rv
join srdb.dbo.clients c
  on c.corp_id = rv.corporationid
where rv.primarydda is not null
  and rv.memoname like '%Branch%'
  and rv.issuedate is not null
  and (@since is null or rv.issuedate >= @since)
  and (not exists (select 1 from @client_list) or c.client_id in (select client_id from @client_list));

if object_id('tempdb..#referrals') is not null drop table #referrals;
create table #referrals (
    client_id        int,
    client_name      varchar(200),
    corporation_id   varchar(50),
    primarydda       varchar(50),
    issue_date       datetime,
    branch_number    varchar(20),
    branch_name      varchar(200),
    account_found    char(1),
    name1            varchar(200),
    date_opened      date,
    has_debitcard    varchar(10),
    rege_response    varchar(100),
    total_spend      decimal(18, 2),
    total_fees       decimal(18, 2),
    total_svcchg     decimal(18, 2),
    total_othchg     decimal(18, 2),
    total_nsf        decimal(18, 2),
    balance_period   date,
    balance_average  decimal(18, 2),
    balance_current  decimal(18, 2)
);

declare @id int, @name varchar(200), @db sysname, @sql nvarchar(max);

declare client_cursor cursor local fast_forward for
    select client_id, client_name from @clients order by client_id;
open client_cursor;
fetch next from client_cursor into @id, @name;

while @@fetch_status = 0
begin
    set @db = 'a' + cast(@id as varchar(10));

    if db_id(@db) is null
        print concat('Skipped ', @id, ' ', @name, ': no database ', @db);
    else
    begin
        set @sql = N'
        declare @h_max_period date = (select max(period) from ' + quotename(@db) + N'.dbo.history_account);

        insert #referrals
        select
            c.client_id,
            c.name,
            rv.corporationid,
            rv.primarydda,
            rv.issuedate,
            b.BANKBRANCHID,
            b.name,
            case when a.account_id is null then ''N'' else ''Y'' end,
            a.name1,
            a.date_opened,
            a.has_debitcard,
            a.rege_response,
            isnull(ha.total_spend, 0),
            isnull(ha.nsf_od_fees, 0),
            isnull(ha.service_charges, 0),
            isnull(ha.other_charges, 0),
            isnull(ha.sum_nsf, 0),
            @h_max_period,
            hm.balance_average,
            hm.balance_current
        from MRDB..MIGRATION.GETICREFERRALSVIEWPLUSMEMO rv
        join srdb.dbo.clients c
          on c.corp_id = rv.corporationid
         and c.client_id = @id
        left join ' + quotename(@db) + N'.dbo.accounts a
          on a.account_number = rv.primarydda
        left join MRDB..MIGRATION.BRANCH b
          on b.CORPORATIONID = rv.CORPORATIONID
         and rv.CONTENTS = trim(cast(b.BANKBRANCHID as varchar(20)))
         and b.ISACTIVE = 1
        left join (
            select h.account_id,
                   sum(h.total_amount) total_spend,
                   sum(h.fees1)        nsf_od_fees,
                   sum(h.fees2)        service_charges,
                   sum(h.fees3)        other_charges,
                   sum(h.nsf)          sum_nsf
            from ' + quotename(@db) + N'.dbo.history_account h
            group by h.account_id
        ) ha
          on ha.account_id = a.account_id
        left join ' + quotename(@db) + N'.dbo.history_account hm
          on hm.account_id = a.account_id
         and hm.period = @h_max_period
        where rv.primarydda is not null
          and rv.memoname like ''%Branch%''
          and rv.issuedate is not null
          and (@since is null or rv.issuedate >= @since)
          and (@opened_only = 0 or a.date_opened is not null);';

        begin try
            exec sp_executesql @sql, N'@id int, @since date, @opened_only bit',
                 @id = @id, @since = @since, @opened_only = @opened_only;
            print concat(@id, ' ', @name, ': ', @@rowcount, ' referrals');
        end try
        begin catch
            print concat('Failed ', @id, ' ', @name, ': ', error_message());
        end catch
    end

    fetch next from client_cursor into @id, @name;
end

close client_cursor;
deallocate client_cursor;

select *
from #referrals
order by client_id, issue_date, primarydda;

-- Summary by client
select client_id, client_name,
       count(*)                                          referrals,
       sum(case when account_found = 'Y' then 1 else 0 end) accounts_found,
       min(issue_date)                                   first_issue,
       max(issue_date)                                   last_issue
from #referrals
group by client_id, client_name
order by client_id;
