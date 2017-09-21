#!/usr/bin/env ruby
$LOAD_PATH.unshift File.realpath(File.expand_path('../../lib', __FILE__))

#
# Scans committee pages for compliance with requirements and recommendations:
#   https://www.apache.org/foundation/marks/pmcs#navigation
#   http://www.apache.org/events/README.txt
#
# Makes no value judgements.  Simply extracts raw data for offline analysis.
#

require 'whimsy/asf'
require 'net/http'
require 'nokogiri'
require 'json'

require 'whimsy/cache'

def squash(text)
  text.scrub.gsub(/[[:space:]]+/, ' ').strip
end

#########################################################################

IMAGE_DIR = ASF::SVN.find('asf/infrastructure/site/trunk/content/img')

def parse(id, site, name)
  uri = URI.parse(site)
    
  # default data
  data = {
    display_name: name,
    uri: site,
    events: nil,
    foundation: nil,
    license: nil,
    sponsorship: nil,
    security: nil,
    trademarks: nil,
    copyright: nil,
    image: nil,
  }

  # check if site exists
  begin
    Socket.getaddrinfo(uri.host, uri.scheme)
  rescue SocketError
    return data
  end

  uri, response, status = $cache.get(site.to_s)
  $stderr.puts "#{id} #{uri} #{status}"
  doc = Nokogiri::HTML(response)
  data[:uri] = uri.to_s

  # scan each link
  doc.css('a').each do |a|

    # check the link targets
    a_href = a['href'].to_s.strip

    if a_href =~ %r{^https?://(www\.)?apache\.org/?$}
      img = a.at('img')
      if img
        # use the title (hover text) in preference to the source
        data[:foundation] = img['title'] ? squash(img['title']) : uri + img['src'].strip
      else
        data[:foundation] = squash(a.text) 
      end
    end

    if a_href.include? 'apache.org/events/'
      img = a.at('img')
      if img
        data[:events] = uri + img['src'].strip
      else
        data[:events] = uri + a_href
      end
    end

    # check the link text
    a_text = a.text.downcase.strip
    $stderr.puts a_text if $verbose

    if a_text =~ /licenses?/ and a_href.include? 'apache.org'
      begin
        data[:license] = uri + a_href 
      rescue
        data[:license] = a_href
      end
    end

    if a_text == 'thanks'
      begin
        data[:thanks] = uri + a_href 
      rescue
        data[:thanks] = a_href
      end
    end

    if a_text == 'security'
      begin
        data[:security] = uri + a_href 
      rescue
        data[:security] = a_href
      end
    end

    if ['sponsorship', 'donate', 'sponsor apache','sponsoring apache'].include? a_text
      begin
        data[:sponsorship] = uri + a_href
      rescue
        data[:sponsorship] = a_href
      end
    end
  end

  # Now scan the page text
  doc.traverse do |node|
    next unless node.is_a?(Nokogiri::XML::Text)

    txt = squash(node.text)

    # allow override if phrase looks good
    if (txt =~ /\btrademarks\b/  and not data[:trademarks]) or txt =~/are trademarks of [Tt]he Apache Software/
      t, p = getText(txt, node)
      # drop previous text if it looks like Copyright sentence
      data[:trademarks] = t.sub(/^.*?Copyright .+? Foundation[.]?/,'').strip
      data[:tradeparent] = p if p
    end
    if txt =~ /Copyright / or txt =~ /©/
      t, p = getText(txt, node)
      # drop text around the Copyright (or the symbol)
      data[:copyright] = t.sub(/^.*?((Copyright|©) .+? Foundation[.]?).*/,'\1').strip
      data[:copyparent] = p if p
    end
  end

  # see if image has been uploaded
  if IMAGE_DIR
    data[:image] = Dir["#{IMAGE_DIR}/#{id}.*"].
      map {|path| File.basename(path)}.first
  end

  return data
end

# get the text; use parent if text does not appear to be complete
def getText(txt, node)
  parent = nil # debug to show where parent needed to be fetched
  if not txt =~ /Apache Software Foundation/i # have we got all the text?
    if node.parent.name == 'a' # e.g. whimsical. such parents don't have extra text.
      newnode = node.parent.parent
    else
      newnode = node.parent
    end
    # ensure <br> is treated as a separator when extracting the combined text
    newnode.css('br').each{ |br| br.replace(" ") }
    txt = squash(newnode.text)
    parent = true
  end
  return txt, parent
end

$verbose = ARGV.delete '--verbose'

results = {}

$cache = Cache.new(dir: 'site-scan')

# Parse a single site given its URL
if ARGV.length == 2 and ARGV.first =~ /^https?:/
  site = ARGV.shift
  name = ARGV.shift
  results[name] = parse(name, site, name)
else
  if ARGV.first =~ %r{[./]} # have we a file name?
    outfile = ARGV.shift
  else
    outfile = nil
  end
  # scan all committees, including non-pmcs
  ASF::Committee.load_committee_info
  committees = (ASF::Committee.pmcs + ASF::Committee.nonpmcs).uniq
  
  committees.sort_by {|committee| committee.name}.each do |committee|
    next unless committee.site
    # if parameters specified, parse only those names
    if ARGV.length > 0
      next unless ARGV.include? committee.name
    end

    # fetch, parse committee site
    results[committee.name] = parse(committee.name, committee.site, committee.display_name)
  end
end

# Output results
if outfile
  File.write(outfile, JSON.pretty_generate(results))
else
  puts JSON.pretty_generate(results)
end
