#!/usr/bin/env ruby
PAGETITLE = "Members@ Mailing List Statistics" # Wvisible:members
$LOAD_PATH.unshift '/srv/whimsy/lib'

require 'wunderbar'
require 'wunderbar/bootstrap'
require 'wunderbar/jquery'
require 'whimsy/asf'
require 'whimsy/asf/agenda'
require 'date'
require 'mail'
require '../../tools/mboxhdr2csv.rb'

user = ASF::Person.new($USER)
unless user.asf_member?
  print "Status: 401 Unauthorized\r\n"
  print "WWW-Authenticate: Basic realm=\"ASF Members\"\r\n\r\n"
  exit
end

# Return sorted data in JSON format if the query string includes 'json'
ENV['HTTP_ACCEPT'] = 'application/json' if ENV['QUERY_STRING'].include? 'json'

LIST_ROOT = 'members'
SRV_MAIL = "/srv/mail/#{LIST_ROOT}"

WEEK_TOTAL = '@@total' # Use @@ so it can't match who name/emails
WEEK_START = '@@start'

# Display monthly statistics for all available data
def display_monthly(months:, nondiscuss:)
  months.sort.reverse.each do |month|
    data = MailUtils.get_mails_month(mailroot: SRV_MAIL, yearmonth: month, nondiscuss: nondiscuss)
    next if data.empty?
    _h1 "#{LIST_ROOT}@ statistics for #{month} (total mails: #{data[MailUtils::MAILS].length})", id: "#{month}"
    _div.row do
      _div.col_sm_6 do
        _ul.list_group do
          _li.list_group_item.active.list_group_item_info "Top Ten Email Senders"
          ctr = 0
          data[MailUtils::MAILCOUNT].each do |id, num|
            if num > (data[MailUtils::MAILS].length / 10)
              _li.list_group_item.list_group_item_warning "#{id} wrote: #{num}"
            else
              _li.list_group_item "#{id} wrote: #{num}"
            end
            ctr += 1
            break if ctr >= 10
          end
        end   
      end
      _div.col_sm_6 do
        _ul.list_group do
          _li.list_group_item.list_group_item_info "Long Tail - All Senders"
          _li.list_group_item do
            data[MailUtils::MAILCOUNT].each do |id, num|
              _! "#{id} (#{num}), "
            end
          end
        end
      end
    end
  end
end

# Display weekly statistics for non-tool emails
def display_weekly(months:, nondiscuss:)
  weeks = Hash.new {|h, k| h[k] = {}}
  months.sort.each do |month|
    data = MailUtils.get_mails_month(mailroot: SRV_MAIL, yearmonth: month, nondiscuss: nondiscuss)
    next if data.empty?
    # accumulate all mails in order for weeks, through all months
    data[MailUtils::MAILS].each do |m|
      d = Date.parse(m['date'])
      wn = d.strftime('%G-W%V')
      if weeks.has_key?(wn)
        weeks[wn][m['who']] +=1
      else
        weeks[wn] = Hash.new{ 0 }
        weeks[wn][m['who']] = 1
      end
    end
  end
  _h1 "#{LIST_ROOT}@ list emails weekly statistics", id: "top"
  _div.row do
    _div.col.col_sm_offset_1.col_sm_9 do
      weeks.sort.reverse.each do |week, senders|
        total = 0
        senders.each do |sender, count|
          next if /@@/ =~ sender
          total += count
        end
        senders[WEEK_TOTAL] = total
        _ul.list_group do
          _li.list_group_item.active.list_group_item_info "Week #{week} Top Senders (total mails: #{senders[WEEK_TOTAL]})", id: "#{week}"
          ctr = 0
          senders.sort_by {|k,v| -v}.to_h.each do |id, num|
            next if /@@/ =~ id
            if (num > 7) && (num > (senders[WEEK_TOTAL] / 5)) # Ignore less than one per day 
              _li.list_group_item.list_group_item_danger "#{id} wrote: #{num}"
            elsif (num > 7) && (num > (senders[WEEK_TOTAL] / 10))
              _li.list_group_item.list_group_item_warning "#{id} wrote: #{num}"
            elsif (num > 7) && (num > (senders[WEEK_TOTAL] / 20))
              _li.list_group_item.list_group_item_info "#{id} wrote: #{num}"
            else
              _li.list_group_item "#{id} wrote: #{num}"
            end
            ctr += 1
            break if ctr >= 5
          end
        end
      end
    end
  end
end

# produce HTML
_html do
  _body? do
    _whimsy_body(
      title: PAGETITLE,
      related: {
        "/members/index" => "More Member-Specific Tools",
        "/officers/list-traffic" => "Board@ List Traffic",
        "#{ENV['SCRIPT_NAME']}" => "Members@ List Traffic By Month",
        "#{ENV['SCRIPT_NAME']}?week" => "Members@ List Traffic By Week",
        "https://github.com/apache/whimsy/blob/master/www#{ENV['SCRIPT_NAME']}" => "See This Source Code"
      },
      helpblock: -> {
        _p %{
          This script displays simple (and likely slightly lossy) analysis of traffic on the #{LIST_ROOT}@ mailing list.
          In particular, mapping From: email to a committer may not work (meaning individual senders may have multiple spots),
          and Subject lines displayed may be truncated (meaning threads may not fully be tracked).  Work in progress.
        }
        _p do
          _ 'Senders of more than 10% of all emails in a month are highlighted. '
          _ 'Senders of more than 20%, 10%, or 5% of all emails in a week are highlighted in the '
          _a 'By week view (supply ?week in URL).', href: '?week'
        end

      }
    ) do
      months = Dir["#{SRV_MAIL}/*"].map {|path| File.basename(path).untaint}.grep(/^\d+$/)
      _.error "HACK - server log one"

      if ENV['QUERY_STRING'].include? 'week'
        display_weekly(months: months, nondiscuss: MailUtils::NONDISCUSSION_SUBJECTS["<#{LIST_ROOT}.apache.org>"])
      else
        display_monthly(months: months, nondiscuss: MailUtils::NONDISCUSSION_SUBJECTS["<#{LIST_ROOT}.apache.org>"])
      end
    end
  end
end

# Return just sorted data counts as JSON
_json do
  months = Dir["#{SRV_MAIL}/*"].map {|path| File.basename(path).untaint}.grep(/^\d+$/)
  data = Hash.new {|h, k| h[k] = {} }
  months.sort.reverse.each do |month|
    tmp = MailUtils.get_mails_month(mailroot: SRV_MAIL, yearmonth: month, nondiscuss: MailUtils::NONDISCUSSION_SUBJECTS["<#{LIST_ROOT}.apache.org>"])
    next if tmp.empty?
    data[month][MailUtils::TOOLCOUNT] = tmp[MailUtils::TOOLCOUNT]
    data[month][MailUtils::MAILCOUNT] = tmp[MailUtils::MAILCOUNT]
  end
  data
end